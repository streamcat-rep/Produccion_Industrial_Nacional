"""Cliente de la Encuesta Industrial Anual de Productos (EIAP) del INE.

El INE no publica la serie histórica por producto en su API JSON (Tempus): solo
está en la aplicación web https://www.ine.es/eip/. Este módulo la consulta igual
que lo haría un navegador:

  1. La página de resultados lista los años disponibles (cada uno con un id interno).
  2. Al abrir un año, la sesión queda fijada a ese año y se listan sus 79 sectores.
  3. Se piden los sectores por lotes y se lee la tabla HTML resultante.

Solo usa la biblioteca estándar.
"""
from __future__ import annotations

import html
import http.cookiejar
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

BASE = "https://www.ine.es"
URL_RESULTADOS = (
    BASE + "/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736149053"
    "&menu=resultados&idp=1254735576715"
)
USER_AGENT = "anprod-eiap/1.0 (uso estadistico; python-urllib)"
LOTE_SECTORES = 10  # la aplicación rechaza consultas de ~20 sectores o más
REINTENTOS = 4

# Las dos encuestas que conviven en la página de resultados.
SERIE_ANTIGUA = "antigua"  # 2008-2021, antigua EIAP
SERIE_NUEVA = "nueva"  # 2021 en adelante, Reglamento (UE) 2019/2152


@dataclass
class Edicion:
    """Un año publicado dentro de una de las dos series."""

    anyo: int
    serie: str
    sel_year: str


@dataclass
class Fila:
    """Un producto en un año concreto, tal y como lo publica el INE."""

    anyo: int
    serie: str
    sector: str  # código de sector EIAP, p. ej. "03"
    sector_nombre: str
    cnae: str
    prodcom: str
    ruta: list[str]  # jerarquía de denominaciones hasta el producto
    unidad: str
    cantidad: float | None  # None = dato no publicado (secreto o no disponible)
    valor: float | None  # miles de euros
    # False si la ruta viene de la exportación de respaldo, que no separa los niveles
    ruta_completa: bool = True


def _abrir(opener, url: str, datos: bytes | None = None, timeout: int = 180) -> str:
    ultimo: Exception | None = None
    for intento in range(REINTENTOS):
        try:
            pet = urllib.request.Request(url, data=datos, headers={"User-Agent": USER_AGENT})
            with opener.open(pet, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as exc:  # red inestable o 5xx puntual: reintentar
            ultimo = exc
            time.sleep(2 * (intento + 1))
    raise RuntimeError(f"No se pudo descargar {url}: {ultimo}") from ultimo


def _sesion():
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )


def listar_ediciones() -> list[Edicion]:
    """Descubre los años publicados leyendo la página de resultados del INE."""
    pagina = _abrir(_sesion(), URL_RESULTADOS)
    ediciones: list[Edicion] = []
    for bloque in re.findall(r"<select[^>]*name=\"url\".*?</select>", pagina, re.S):
        opciones = re.findall(r"selYear=(\d+)[^\"]*\">\s*(\d{4})\s*<", bloque)
        if not opciones:
            continue
        anyos = [int(a) for _, a in opciones]
        # La serie antigua es la que arranca en 2008; la nueva arranca en 2021.
        serie = SERIE_ANTIGUA if min(anyos) < 2021 else SERIE_NUEVA
        ediciones += [Edicion(int(a), serie, sel) for sel, a in opciones]
    if not ediciones:
        raise RuntimeError("La página del INE no lista ningún año: ¿ha cambiado su formato?")
    return sorted(ediciones, key=lambda e: (e.anyo, e.serie))


def _texto(fragmento: str) -> str:
    sin_etiquetas = re.sub(r"<!--.*?-->|<[^>]+>", " ", fragmento, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(sin_etiquetas)).strip()


def _numero(celda: str) -> float | None:
    """'1.390.526' -> 1390526.0 ; '.' o vacío (secreto / no disponible) -> None."""
    txt = _texto(celda).replace(".", "").replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return None


_RE_SECTOR = re.compile(
    r'class="sNombre">(?P<nombre>.*?)</div>.*?class="sCodigo">(?P<codigo>.*?)</div>'
    r'.*?class="sCNAE">(?P<cnae>.*?)</div>(?P<cuerpo>.*?)(?=class="sNombre">|\Z)',
    re.S,
)
_RE_FILA = re.compile(r"<tr>(.*?)</tr>", re.S)
_RE_CELDA = re.compile(r"<td([^>]*)>(.*?)</td\s*>", re.S)


def _parsear(pagina: str, ed: Edicion) -> list[Fila]:
    filas: list[Fila] = []
    for sec in _RE_SECTOR.finditer(pagina):
        codigo = re.sub(r"\D", "", _texto(sec["codigo"]))
        cnae = re.sub(r"^CNAE\s*", "", _texto(sec["cnae"]))
        nombres: dict[str, str] = {}  # id de nodo -> denominación
        for tr in _RE_FILA.finditer(sec["cuerpo"]):
            celdas = _RE_CELDA.findall(tr.group(1))
            if len(celdas) < 5:
                continue
            attrs, nombre = celdas[0]
            ident = re.search(r'id="f_([\d_]+)"', attrs)
            if not ident:
                continue
            nodos = [n for n in ident.group(1).split("_") if n]
            nombres[nodos[-1]] = _texto(nombre)
            prodcom = _texto(celdas[1][1])
            if "producto" not in attrs or not prodcom:
                continue  # fila de agrupación, sin datos
            filas.append(
                Fila(
                    anyo=ed.anyo,
                    serie=ed.serie,
                    sector=codigo,
                    sector_nombre=_texto(sec["nombre"]),
                    cnae=cnae,
                    prodcom=prodcom,
                    ruta=[nombres.get(n, "") for n in nodos],
                    unidad=_texto(celdas[2][1]),
                    cantidad=_numero(celdas[3][1]),
                    valor=_numero(celdas[4][1]),
                )
            )
    return filas


def _consultar(sesion, ids: list[str]) -> str:
    cuerpo = urllib.parse.urlencode(
        [("selYear", "")] + [("selectMultiple", s) for s in ids] + [("consultar", "Consultar")]
    ).encode()
    return _abrir(sesion, f"{BASE}/eip/publicacionForm.do", cuerpo)


def _respaldo_tsv(sesion, ed: Edicion, ident: str, codigo: str, nombre: str) -> list[Fila]:
    """Exportación de texto del INE para un sector cuya tabla HTML no carga.

    Trae los mismos datos pero con la jerarquía fundida en una sola frase.
    """
    url = (f"{BASE}/eip/publicacionForm.do?descargar=1&tipo=1&selYear="
           f"&selectMultiple={ident}&consultar=Consultar")
    pet = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with sesion.open(pet, timeout=300) as resp:
        texto = resp.read().decode("cp1252", "replace")
    if not texto.startswith("PRODCOM"):
        return []
    filas: dict[tuple[str, str], Fila] = {}
    for linea in texto.splitlines()[1:]:
        campos = linea.split("\t")
        if len(campos) < 6 or campos[4].strip() != str(ed.anyo):
            continue
        prodcom, denominacion, tipo, unidad, _, dato = (c.strip() for c in campos[:6])
        fila = filas.setdefault((prodcom, denominacion), Fila(
            anyo=ed.anyo, serie=ed.serie, sector=codigo, sector_nombre=nombre, cnae="",
            prodcom=prodcom, ruta=[denominacion], unidad="---", cantidad=None, valor=None,
            ruta_completa=False))
        if tipo == "CANTIDAD":
            fila.unidad, fila.cantidad = unidad, _numero(dato)
        elif tipo == "VALOR":
            fila.valor = _numero(dato)
    return list(filas.values())


def descargar_edicion(ed: Edicion, progreso=None) -> list[Fila]:
    """Descarga todos los productos de un año (una sesión propia por año)."""
    sesion = _sesion()
    portada = _abrir(sesion, f"{BASE}/eip/anyoForm.do?selYear={ed.sel_year}&consultar=Consultar")
    if f"&nbsp;{ed.anyo}" not in portada:
        raise RuntimeError(f"El INE no devolvió el año {ed.anyo} (selYear={ed.sel_year})")
    # (id interno, código de sector, nombre)
    sectores = re.findall(r'<option value="(\d+)">\s*Sector\s+(\d+):\s*(.*?)\s*</option>', portada, re.S)
    if not sectores:
        raise RuntimeError(f"Año {ed.anyo}: no se encontraron sectores")
    filas: list[Fila] = []
    for i in range(0, len(sectores), LOTE_SECTORES):
        lote = sectores[i : i + LOTE_SECTORES]
        pagina = _consultar(sesion, [s[0] for s in lote])
        if pagina.count('class="sNombre"') == len(lote):
            filas += _parsear(pagina, ed)
        else:
            # Un solo sector defectuoso deja vacío el lote entero: se piden de uno en uno.
            for ident, codigo, nombre in lote:
                pagina = _consultar(sesion, [ident])
                if 'class="sNombre"' in pagina:
                    filas += _parsear(pagina, ed)
                    continue
                respaldo = _respaldo_tsv(sesion, ed, ident, codigo, html.unescape(nombre))
                if not respaldo:
                    raise RuntimeError(f"Año {ed.anyo}: el sector {codigo} no devuelve datos")
                filas += respaldo
        if progreso:
            progreso(ed, min(i + LOTE_SECTORES, len(sectores)), len(sectores))
    return filas
