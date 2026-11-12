"""Tablas input-output del INE (Contabilidad Nacional Anual de España).

El INE publica un libro Excel por año (cne_tio_AA.xlsx). De él solo hace falta la
«Tabla 2. Tabla input-output de la producción interior» a precios básicos,
producto por producto (64 × 64), con su demanda final:

  - z[i][k]: lo que la rama k compra del producto i fabricado en España.
  - consumo, capital, export: demanda final de cada producto (hogares + ISFLSH +
    AAPP; formación bruta de capital; exportaciones).
  - x: producción interior total de cada producto (= intermedia + final).

Es la tabla interior, sin importaciones, que es lo que corresponde al PIB.
Unidad: millones de euros. Solo usa la biblioteca estándar: un .xlsx es un zip
de XML.
"""
from __future__ import annotations

import io
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

BASE = "https://www.ine.es"
URL_RESULTADOS = (
    BASE + "/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177058"
    "&menu=resultados&idp=1254735576581"
)
USER_AGENT = "anprod-eiap/1.0 (uso estadistico; python-urllib)"
HOJA = "Tabla2"
RAMAS = 64

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _descargar(url: str) -> bytes:
    ultimo_error: Exception | None = None
    for intento in range(4):
        try:
            pet = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(pet, timeout=180) as resp:
                return resp.read()
        except Exception as exc:
            ultimo_error = exc
            time.sleep(2 * (intento + 1))
    raise RuntimeError(f"No se pudo descargar {url}: {ultimo_error}") from ultimo_error


def listar_anyos() -> dict[int, str]:
    """Año -> URL del libro Excel, según la página de resultados del INE."""
    pagina = _descargar(URL_RESULTADOS).decode("utf-8", "replace")
    enlaces = re.findall(r'href="([^"]*cne_tio_(\d\d)\.xlsx)"', pagina)
    if not enlaces:
        raise RuntimeError("La página del INE ya no enlaza las tablas input-output (cne_tio_AA.xlsx)")
    return {2000 + int(aa): BASE + ruta if ruta.startswith("/") else ruta for ruta, aa in enlaces}


def _columna(ref: str) -> int:
    n = 0
    for letra in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(letra) - 64
    return n - 1


def _hoja(libro: bytes, nombre: str) -> dict[int, dict[int, object]]:
    """Celdas de una hoja: fila -> {columna: valor} (índices desde 0)."""
    z = zipfile.ZipFile(io.BytesIO(libro))
    cadenas = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(_NS + "si"):
            cadenas.append("".join(t.text or "" for t in si.iter(_NS + "t")))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    destino = None
    for hoja in ET.fromstring(z.read("xl/workbook.xml")).find(_NS + "sheets"):
        if hoja.get("name") == nombre:
            destino = "xl/" + rels[hoja.get(_REL)].lstrip("/").removeprefix("xl/")
    if destino is None:
        raise RuntimeError(f"El libro del INE no tiene la hoja {nombre}")
    filas: dict[int, dict[int, object]] = {}
    for c in ET.fromstring(z.read(destino)).iter(_NS + "c"):
        v = c.find(_NS + "v")
        if v is None or v.text is None:
            continue
        if c.get("t") == "s":
            valor: object = cadenas[int(v.text)]
        else:
            try:
                valor = float(v.text)
            except ValueError:
                valor = v.text
        ref = c.get("r")
        filas.setdefault(int(re.search(r"\d+", ref).group()) - 1, {})[_columna(ref)] = valor
    return filas


class SinDemandaFinal(RuntimeError):
    """El libro de ese año no trae la demanda final junto a la tabla interior."""


def _norm(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto)).strip().lower()


def leer(libro: bytes) -> dict:
    """Extrae del libro Excel la tabla interior: z, demanda final y producción."""
    filas = _hoja(libro, HOJA)
    # Fila de códigos de columna: 1, 2, …, 64 sobre las ramas compradoras.
    fila_cod = next(
        f for f in sorted(filas)
        if sum(isinstance(v, float) and v == int(v) and 1 <= v <= RAMAS for v in filas[f].values()) >= RAMAS
    )
    col_num = {int(v): c for c, v in filas[fila_cod].items() if isinstance(v, float) and 1 <= v <= RAMAS}
    # Los alquileres imputados van en una columna y una fila propias («44 bis»), sin
    # número: se suman a los servicios inmobiliarios (44), que es su división (68).
    col_rama: dict[int, list[int]] = {}
    rama = 0
    for c in range(col_num[1], col_num[RAMAS] + 1):
        rama = next((n for n, cn in col_num.items() if cn == c), rama)
        col_rama.setdefault(rama, []).append(c)
    cabecera = {_norm(v): c for c, v in filas[fila_cod - 1].items() if isinstance(v, str)}

    def col(titulo: str) -> int:
        if titulo not in cabecera:
            raise SinDemandaFinal(f"La {HOJA} del INE no tiene la columna «{titulo}»")
        return cabecera[titulo]

    c_cons, c_cap = col("total gasto en consumo final"), col("formación bruta de capital")
    c_exp, c_total = col("total exportaciones"), col("total empleos")

    nombres: dict[int, str] = {}
    productos: dict[int, list[dict]] = {}
    for f in sorted(filas):
        etiqueta = next((v for v in filas[f].values() if isinstance(v, str)), "")
        m = re.match(r"\s*(\d+)( bis)?\.\s+(.*)", etiqueta)
        if f > fila_cod and m and 1 <= int(m.group(1)) <= RAMAS:
            productos.setdefault(int(m.group(1)), []).append(filas[f])
            if not m.group(2):
                nombres[int(m.group(1))] = m.group(3).strip()
    if len(nombres) != RAMAS or len(col_rama) != RAMAS:
        raise RuntimeError(f"La {HOJA} del INE no tiene {RAMAS} productos × {RAMAS} ramas")

    def num(i: int, columnas: list[int]) -> float:
        valores = (fila.get(c, 0.0) for fila in productos[i] for c in columnas)
        return round(sum(float(v) for v in valores if isinstance(v, (int, float))), 4)

    orden = range(1, RAMAS + 1)
    tabla = {
        "nombres": [nombres[i] for i in orden],
        "z": [[num(i, col_rama[k]) for k in orden] for i in orden],
        "consumo": [num(i, [c_cons]) for i in orden],
        "capital": [num(i, [c_cap]) for i in orden],
        "export": [num(i, [c_exp]) for i in orden],
        "x": [num(i, [c_total]) for i in orden],
    }
    # Comprobación contable: intermedia + final = total de empleos de cada producto.
    for i in range(RAMAS):
        suma = sum(tabla["z"][i]) + tabla["consumo"][i] + tabla["capital"][i] + tabla["export"][i]
        if abs(suma - tabla["x"][i]) > max(1.0, 1e-4 * abs(tabla["x"][i])):
            raise RuntimeError(f"La {HOJA} no cuadra en el producto {i + 1}: {suma:.1f} ≠ {tabla['x'][i]:.1f}")
    return tabla


def descargar() -> dict[str, dict]:
    """Tablas publicadas con demanda final: año (como texto) -> tabla.

    Los libros de 2016 a 2020 solo traen los consumos intermedios de la tabla
    interior, sin la demanda final, así que no sirven para este reparto.
    """
    tablas = {}
    for anyo, url in sorted(listar_anyos().items()):
        try:
            tablas[str(anyo)] = leer(_descargar(url))
        except SinDemandaFinal:
            continue
    if not tablas:
        raise RuntimeError("Ninguna tabla input-output del INE trae ya la demanda final")
    return tablas
