"""PIB y asalariados del INE, para calcular la productividad media y la de cada rama.

Fuentes (API JSON del INE, Tempus):
  - Tabla 67821: PIB y VAB por ramas, trimestral, precios corrientes (millones de euros).
  - Tabla 65988: asalariados por rama de actividad, media anual (miles de personas).

El PIB se anualiza sumando los cuatro trimestres (datos sin ajustar de
estacionalidad, que son los que suman el total anual). Un año con menos de
cuatro trimestres publicados se descarta.

La tabla del PIB solo desglosa la industria en "manufacturera (C)" e "industria
(B-E)", así que esas son las ramas que se pueden calcular:
  - C:   industria manufacturera.
  - BDE: extractivas, energía y agua = industria (B-E) menos manufacturera (C).
"""
from __future__ import annotations

import json
import time
import urllib.request
from collections import defaultdict

API = "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{tabla}?nult={n}&tip=AM"
TABLA_PIB = 67821
TABLA_ASALARIADOS = 65988
USER_AGENT = "anprod-eiap/1.0 (uso estadistico; python-urllib)"

# Códigos del INE dentro de cada tabla.
PIB_TOTAL = "B1GQ"
VAB_INDUSTRIA = "B1b_I09"  # secciones B a E
VAB_MANUFACTURERA = "B1b_S09_C"  # sección C

RAMAS = {
    "C": "Industria manufacturera",
    "BDE": "Industrias extractivas, energía y agua",
}


def rama_de(cnae: str) -> str:
    """Rama de un sector de la EIAP a partir de su CNAE ('35.15/16' -> 'BDE')."""
    try:
        division = int(cnae.strip()[:2])
    except ValueError:
        return "C"
    return "C" if 10 <= division <= 33 else "BDE"


def _tabla(tabla: int, ultimos: int) -> list[dict]:
    url = API.format(tabla=tabla, n=ultimos)
    ultimo_error: Exception | None = None
    for intento in range(4):
        try:
            pet = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(pet, timeout=180) as resp:
                return json.load(resp)
        except Exception as exc:
            ultimo_error = exc
            time.sleep(2 * (intento + 1))
    raise RuntimeError(f"No se pudo descargar la tabla {tabla} del INE: {ultimo_error}") from ultimo_error


def _meta(serie: dict) -> dict[str, tuple[str, str]]:
    """Variable -> (nombre, código) de una serie."""
    return {m["T3_Variable"].strip(): (m["Nombre"], m.get("Codigo") or "") for m in serie["MetaData"]}


def _pib_anual() -> dict[str, dict[int, float]]:
    """Código del agregado -> {año: millones de euros}, solo años con 4 trimestres."""
    anual: dict[str, dict[int, float]] = {}
    for serie in _tabla(TABLA_PIB, 120):
        meta = _meta(serie)
        if meta["Tipo de dato"][0] != "Dato base":
            continue
        if not meta["Corrección de efectos"][0].startswith("Datos no ajustados"):
            continue
        codigos = {codigo for _, codigo in meta.values()}
        clave = next((c for c in (PIB_TOTAL, VAB_INDUSTRIA, VAB_MANUFACTURERA) if c in codigos), None)
        if not clave:
            continue
        trimestres: dict[int, list[float]] = defaultdict(list)
        for dato in serie["Data"]:
            if dato["Valor"] is not None:
                trimestres[dato["Anyo"]].append(dato["Valor"])
        anual[clave] = {a: sum(v) for a, v in trimestres.items() if len(v) == 4}
    faltan = {PIB_TOTAL, VAB_INDUSTRIA, VAB_MANUFACTURERA} - anual.keys()
    if faltan:
        raise RuntimeError(f"La tabla {TABLA_PIB} del INE ya no trae {sorted(faltan)}")
    return anual


def _asalariados() -> dict[str, dict[int, float]]:
    """'TOTAL' o letra de sección CNAE -> {año: miles de asalariados}."""
    series: dict[str, dict[int, float]] = {}
    for serie in _tabla(TABLA_ASALARIADOS, 40):
        meta = _meta(serie)
        if meta["Sexo"][0] != "Ambos sexos" or meta["Tipo de dato"][0] != "Valor absoluto":
            continue
        if "TOTALES VARIABLES CNAE" in meta:
            clave = "TOTAL"
        elif "SECCIONES" in meta:
            clave = meta["SECCIONES"][1]
        else:
            continue  # divisiones: no hacen falta
        series[clave] = {d["Anyo"]: d["Valor"] for d in serie["Data"] if d["Valor"] is not None}
    faltan = {"TOTAL", "B", "C", "D", "E"} - series.keys()
    if faltan:
        raise RuntimeError(f"La tabla {TABLA_ASALARIADOS} del INE ya no trae {sorted(faltan)}")
    return series


def descargar() -> dict:
    pib, asal = _pib_anual(), _asalariados()
    anyos = sorted(set(pib[PIB_TOTAL]) & set(asal["TOTAL"]))
    if not anyos:
        raise RuntimeError("El PIB y los asalariados del INE no coinciden en ningún año")
    return {
        "anyos": anyos,
        "pib": [pib[PIB_TOTAL][a] for a in anyos],
        "asalariados": [asal["TOTAL"][a] for a in anyos],
        "ramas": {
            "C": {
                "n": RAMAS["C"],
                "vab": [pib[VAB_MANUFACTURERA][a] for a in anyos],
                "asalariados": [asal["C"][a] for a in anyos],
            },
            "BDE": {
                "n": RAMAS["BDE"],
                "vab": [round(pib[VAB_INDUSTRIA][a] - pib[VAB_MANUFACTURERA][a], 1) for a in anyos],
                "asalariados": [round(asal["B"][a] + asal["D"][a] + asal["E"][a], 1) for a in anyos],
            },
        },
    }
