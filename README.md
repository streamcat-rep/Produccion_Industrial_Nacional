# Producción industrial de España por producto (INE)

Web estática con la producción de cada producto industrial en España —cantidad
fabricada y valor económico— desde 2008, a partir de la
[Encuesta Industrial Anual de Productos del INE](https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736149053&menu=resultados&idp=1254735576715).

## Qué hay aquí

| Ruta | Para qué |
| --- | --- |
| `index.html` | La web. Sin dependencias ni compilación. |
| `data/produccion.json` | Los datos que lee la web. |
| `data/crudo/` | Copia comprimida de lo descargado del INE, un fichero por año. |
| `scripts/actualizar.py` | Descarga del INE y regenera `data/`. |
| `scripts/ine_eip.py` | Cliente de la aplicación de consulta del INE. |
| `scripts/nombres.py` | Nombres claros, emojis y unidades. **Edítalo para renombrar.** |
| `.github/workflows/actualizar.yml` | Actualización automática en GitHub. |
| `worker/` | Intermediario en Cloudflare que lanza la actualización desde la web. |

## Actualizar los datos

Solo hace falta Python 3.9 o superior; no hay que instalar nada.

```bash
python scripts/actualizar.py                 # todo, de 2008 al último año (10-15 min)
python scripts/actualizar.py --anyos 2025    # solo un año; el resto sale de data/crudo/
python scripts/actualizar.py --sin-descarga  # regenerar el JSON tras tocar nombres.py
```

El script descubre solo qué años ha publicado el INE: cuando salga 2026, basta
con ejecutarlo de nuevo. Si una descarga falla, no toca los datos publicados.

## Verla en local

```bash
python -m http.server 8000
# y abrir http://localhost:8000
```

(Abrir `index.html` con doble clic no funciona: el navegador no deja leer el JSON.)

## Publicarla en GitHub Pages

1. Sube esta carpeta a un repositorio de GitHub.
2. *Settings → Pages → Build and deployment*: **Deploy from a branch**, rama `main`, carpeta `/ (root)`.
3. En *Settings → Actions → General → Workflow permissions* marca **Read and write permissions**
   para que la actualización automática pueda guardar los datos.

### Refrescar los datos desde la web

La web es estática, así que la descarga del INE la hace el workflow
`.github/workflows/actualizar.yml` (unos 15 minutos), que guarda los datos
nuevos en el repositorio. Se lanza de tres formas:

- **Solo**, el día 1 de cada mes.
- **A mano** en GitHub: *Actions → Actualizar datos del INE → Run workflow*.
- **Desde la web**, con el botón **⚡ Actualizar desde el INE**, que puede pulsar
  cualquier visitante. La web no guarda credenciales: llama a un intermediario
  (Cloudflare Worker, carpeta `worker/`) que tiene el token de GitHub como
  secreto y lanza el trabajo. Solo permite una actualización por hora.

El botón **🔄 Recargar** solo vuelve a leer `data/produccion.json` ya publicado,
saltándose la caché del navegador.

## Cómo leer las cifras

- **Valor**: en euros corrientes. El INE lo publica en miles de euros.
- **«—»**: dato no publicado (secreto estadístico o no disponible).
- **0**: ninguna empresa de la muestra fabricó ese producto.
- **2021**: ese año cambió la encuesta (Reglamento UE 2019/2152; solo cuenta lo
  fabricado en territorio español) y el INE publica 2021 con ambas. La web
  muestra el dato nuevo y calcula la variación 2021/2020 con la encuesta
  antigua, que es la comparable.
- Los productos se identifican por su código PRODCOM de 10 dígitos. La lista de
  productos cambia con los años, así que no todos tienen la serie completa.

## El intermediario de Cloudflare

Vive en `worker/` y se despliega con [Wrangler](https://developers.cloudflare.com/workers/wrangler/):

```bash
cd worker
npx wrangler login                    # una vez
npx wrangler deploy                   # publica el worker
npx wrangler secret put GITHUB_TOKEN  # pega el token cuando lo pida
```

El token es uno *fine-grained* de GitHub, limitado a este repositorio y con el
permiso **Actions: Read and write**. Cuando caduque, se crea otro y se repite el
último comando. El límite entre actualizaciones (`MINUTOS_ENTRE_LANZAMIENTOS`) y el
origen permitido están en `worker/wrangler.toml`.
