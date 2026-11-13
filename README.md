# Producción industrial de España por producto (INE)

Web estática con la producción de cada producto industrial en España —cantidad
fabricada y valor económico— desde 2008, a partir de la
[Encuesta Industrial Anual de Productos del INE](https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736149053&menu=resultados&idp=1254735576715).

## Qué hay aquí

| Ruta | Para qué |
| --- | --- |
| `index.html` | La web. Sin dependencias ni compilación. |
| `final.html` | Página «Producción final»: cada producto con sus envases e ingredientes. |
| `data/produccion.json` | Los datos que lee la web. |
| `data/recetas.json` | Las recetas comprobadas (lo lee `final.html`). |
| `data/granja.json` | Trabajo en granjas y campo por euro, y precios en origen (Eurostat; lo lee `final.html`). |
| `data/crudo/` | Copia comprimida de lo descargado del INE, un fichero por año. |
| `scripts/actualizar.py` | Descarga del INE y regenera `data/`. |
| `scripts/ine_eip.py` | Cliente de la aplicación de consulta del INE. |
| `scripts/ine_macro.py` | PIB y asalariados del INE, para la productividad. |
| `scripts/nombres.py` | Nombres claros, emojis y unidades. **Edítalo para renombrar.** |
| `scripts/recetas.py` | Qué lleva cada producto al venderse (bandeja, film, botella…). **Edítalo para afinar.** |
| `scripts/granja.py` | Descarga de Eurostat el trabajo (UTA) y la producción por tipo de explotación, y los precios en origen. |
| `scripts/ine_tio.py` | Tablas input-output del INE. |
| `scripts/destinos.py` | Qué es bien final, qué insumo y de quién. **Edítalo para reclasificar.** |
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

## La vista «Trabajo necesario»

Segunda pestaña de la web. Añade a cada producto cuánto trabajo representa:

| Columna | Cálculo |
| --- | --- |
| Productividad media | PIB anual ÷ total de asalariados (€ por asalariado y año) |
| Productividad de la rama | Valor añadido de la rama ÷ asalariados de la rama |
| Años-persona media / rama | Valor de la producción del producto ÷ productividad |
| TTSN media / industria / rama | (Salario ÷ productividad) × jornada anual, en horas |

- El PIB es trimestral ([tabla 67821](https://ine.es/jaxiT3/Tabla.htm?t=67821&L=0)) y se
  anualiza sumando los cuatro trimestres; un año incompleto no se usa. Los
  asalariados son la media anual de la EPA ([tabla 65988](https://ine.es/jaxiT3/Tabla.htm?t=65988&L=0)).
- La tabla del PIB solo desglosa la industria en dos ramas: **manufacturera**
  (todos los sectores salvo el 79) y **extractivas, energía y agua** (sector 79,
  electricidad y gas), que se obtiene restando la manufacturera al total de industria.
- El **TTSN industria** usa la productividad de toda la industria: valor añadido de
  las secciones B a E entre sus asalariados.
- El salario (2.500 € por defecto) y la jornada anual (1.826 h, el máximo legal
  de 40 h semanales) se pueden cambiar en la propia web.
- El TTSN depende solo de la productividad, así que es el mismo para todos los
  productos de una rama en un año.

## La página «Producción final»

`final.html` toma cada producto final tal como se vende y le suma lo que lleva:
la pechuga de pollo con su bandeja de plástico, su film, su etiqueta, la caja de
cartón y el palé; la cerveza con la malta, la botella, la chapa y la lata. De todo
junto da la cantidad, el valor, los años-persona y el TTSN en minutos por kilo o
litro.

- Las **recetas** están en `scripts/recetas.py`: por kilo o litro de producto,
  cuánto lleva de cada componente, con una nota que explica el cálculo (peso de la
  bandeja, tamaño del envase, parte que sale a granel…). **No son datos del INE**:
  son estimaciones del formato de venta típico, para corregir si hay un dato mejor.
- Cada componente se valora al **precio medio de la misma encuesta** (valor entre
  cantidad) y su trabajo, con la productividad de la rama que lo fabrica.
- **TTSN por unidad**: años-persona de cada producto de la encuesta × jornada ÷ lo
  producido (minutos por kg de pollo, por kg de bandeja, por botella…). El producto
  final suma el trabajo anterior de todo lo que lleva, por kilo y por unidad de
  venta (`VENTA` en `scripts/recetas.py`).
- **Cadena hacia atrás** (`CADENA` en `scripts/recetas.py`): cada componente lleva
  sus materias primas si la encuesta las mide (bandeja → polipropileno → propileno
  → nafta; caja → papel → pasta; lata → hojalata → acero; pienso → harina de soja).
- **Trabajo de cada nodo**: por defecto, valor ÷ valor añadido por asalariado de su
  rama, como en la otra pestaña. Se puede elegir solo el trabajo directo (valor ÷
  producción por asalariado), que no cuenta dos veces lo que el precio ya incluye.
- **Granja y campo** (`GRANJA` en `scripts/recetas.py`, datos en `scripts/granja.py`):
  años-persona = valor en origen ÷ productividad de su tipo de explotación (UTA entre
  producción estándar, Eurostat). Árbol: pollo en piezas → pollo vivo → pienso →
  cereal y soja.
- La página avisa cuando una receta pide más de un componente del que se fabrica
  en España: o se importa (malta, tapones de corcho) o la receta exagera.
- Tras tocar las recetas: `python scripts/recetas.py` (comprueba los códigos y
  escribe `data/recetas.json`).

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
