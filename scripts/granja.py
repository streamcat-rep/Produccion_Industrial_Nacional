#!/usr/bin/env python3
"""Genera data/granja.json: trabajo en las granjas y el campo, y precios en origen.

Uso:
    python scripts/granja.py

La encuesta industrial del INE no mide las granjas ni el campo. Para sumar su
trabajo a la carne, la leche o el pienso se usa la misma regla que en la industria,
años-persona = valor ÷ productividad, con datos de Eurostat para España:

  - Encuesta de Estructura de las Explotaciones Agrarias (ef_m_farmleg): unidades de
    trabajo-año (UTA: una persona a tiempo completo durante un año) y producción
    estándar en euros de cada tipo de explotación. UTA ÷ euros = años-persona por
    euro producido en la granja.
  - Precios percibidos por los agricultores (apri_ap_anouta, apri_ap_crpouta): euros
    por kilo de pollo vivo, de cerdo vivo, de leche cruda, de maíz…

Los nodos (pollo vivo, cereal…) y sus cantidades están en GRANJA de recetas.py.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import recetas

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "data" / "granja.json"
URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{ds}?geo=ES&format=JSON&lang=EN"
USER_AGENT = "anprod-eiap/1.0 (uso estadistico; python-urllib)"


def _json(ds: str) -> dict:
    ultimo_error = None
    for intento in range(4):
        try:
            pet = urllib.request.Request(URL.format(ds=ds), headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(pet, timeout=120) as resp:
                return json.load(resp)
        except Exception as exc:  # red caída o Eurostat ocupado: reintentar
            ultimo_error = exc
            time.sleep(2 * (intento + 1))
    raise RuntimeError(f"No se pudo descargar {ds} de Eurostat: {ultimo_error}")


def _serie(d: dict, fijo: dict[str, str]) -> dict[str, float]:
    """Año -> valor de la celda con las dimensiones fijadas (las demás, la primera)."""
    ids, tam = d["id"], d["size"]
    indice = {k: d["dimension"][k]["category"]["index"] for k in ids}
    serie = {}
    for anyo, pos_t in indice["time"].items():
        plano = 0
        for k, s in zip(ids, tam):
            pos = pos_t if k == "time" else indice[k].get(fijo[k], -1) if k in fijo else 0
            if pos < 0:
                return {}
            plano = plano * s + pos
        valor = d["value"].get(str(plano))
        if valor is not None:
            serie[anyo] = valor
    return serie


def trabajo_por_euro(tipos: set[str]) -> dict[str, dict[str, float]]:
    """Tipo de explotación -> {año: años-persona por millón de euros de producción}."""
    d = _json("ef_m_farmleg")
    resultado = {}
    for tipo in sorted(tipos):
        por_anyo = {}
        # Los censos antiguos dan el total; los recientes, las explotaciones sobre el umbral.
        for estrato in ("TOTAL", "ABVTH"):
            base = {"statinfo": estrato, "leg_form": "TOTAL", "farmtype": tipo, "so_eur": "TOTAL",
                    "uaarea": "TOTAL", "geo": "ES"}
            uta = _serie(d, {**base, "unit": "AWU"})
            euros = _serie(d, {**base, "unit": "EUR"})
            for anyo in uta.keys() & euros.keys():
                if anyo not in por_anyo and euros[anyo] > 0:
                    por_anyo[anyo] = round(uta[anyo] / euros[anyo] * 1e6, 4)
        if not por_anyo:
            raise RuntimeError(f"Eurostat no da trabajo y producción de las explotaciones {tipo}")
        resultado[tipo] = dict(sorted(por_anyo.items()))
    return resultado


def precios() -> dict[str, dict[str, float]]:
    """Alias de GRANJA -> {año: € por kg en origen}."""
    datos = {}
    resultado = {}
    for alias, (nombre, _tipo, ds, codigo, divisor) in recetas.GRANJA.items():
        d = datos.setdefault(ds, _json(ds))
        dim = next(k for k in d["id"] if k.startswith("prod_"))
        serie = _serie(d, {dim: codigo, "currency": "EUR", "geo": "ES"})
        if not serie:
            raise RuntimeError(f"Eurostat no da precios de {nombre} en España")
        resultado[alias] = {a: round(v / divisor, 5) for a, v in sorted(serie.items()) if v > 0}
    return resultado


def generar() -> dict:
    tipos = {t for _n, t, _ds, _c, _d in recetas.GRANJA.values()}
    resultado = {
        "meta": {
            "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fuentes": ["Eurostat ef_m_farmleg: UTA y producción estándar por tipo de explotación, España",
                        "Eurostat apri_ap_anouta y apri_ap_crpouta: precios percibidos por los agricultores, España"],
        },
        "trabajo": trabajo_por_euro(tipos),
        "precios": precios(),
    }
    temporal = SALIDA.with_suffix(".tmp")
    temporal.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(SALIDA)
    return resultado


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    r = generar()
    for tipo, serie in r["trabajo"].items():
        print(f"  {tipo}: {serie} años-persona por M€")
    for alias, serie in r["precios"].items():
        ultimo = max(serie)
        print(f"  {alias}: {serie[ultimo]} €/kg ({ultimo})")
    print(f"Listo → {SALIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
