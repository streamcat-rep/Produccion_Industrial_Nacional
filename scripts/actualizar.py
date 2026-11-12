#!/usr/bin/env python3
"""Actualiza data/produccion.json con la Encuesta Industrial Anual de Productos del INE.

Uso:
    python scripts/actualizar.py                 # vuelve a descargar todos los años
    python scripts/actualizar.py --anyos 2025    # solo ese año; el resto sale de data/crudo/
    python scripts/actualizar.py --sin-descarga  # solo regenera el JSON (p. ej. tras tocar nombres.py)

No necesita instalar nada: solo usa la biblioteca estándar (Python 3.9+).
Los años disponibles se descubren en la web del INE, así que cuando se publique
un año nuevo basta con volver a ejecutarlo.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import dataclasses
import gzip
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import ine_eip
import ine_macro
import produccion_final
from nombres import SECTORES, emoji_de, nombre_de, unidad_clara

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "data" / "produccion.json"
CRUDO = RAIZ / "data" / "crudo"
CRUDO_MACRO = CRUDO / "macro.json"  # PIB y asalariados
HILOS = 6
MIN_PRODUCTOS = 1500  # un año con menos productos indica una descarga rota

# Mismo producto medido en otra escala según el año: se lleva todo a la más reciente.
A_BASE = {
    "t.": ("kg", 1000.0), "kg": ("kg", 1.0), "gramo": ("kg", 0.001),
    "mil unidades": ("ud", 1000.0), "Unidades": ("ud", 1.0),
    "mil pares": ("par", 1000.0), "Pares": ("par", 1.0),
    "mil m2": ("m2", 1000.0), "m2": ("m2", 1.0),
    "mil m3": ("m3", 1000.0), "m3": ("m3", 1.0),
    "mil metros": ("m", 1000.0), "m.": ("m", 1.0),
    "mil litros": ("l", 1000.0), "hectolitro": ("l", 100.0), "Litros": ("l", 1.0),
}


def ruta_crudo(ed: ine_eip.Edicion) -> Path:
    return CRUDO / f"{ed.anyo}-{ed.serie}.json.gz"


def guardar_crudo(ed: ine_eip.Edicion, filas: list[ine_eip.Fila]) -> None:
    CRUDO.mkdir(parents=True, exist_ok=True)
    campos = [
        {k: v for k, v in dataclasses.asdict(f).items() if k not in ("anyo", "serie")}
        for f in filas
    ]
    contenido = json.dumps(campos, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    destino = ruta_crudo(ed)
    # Si el INE no ha cambiado nada no se reescribe el fichero: el mismo contenido
    # comprimido en otra máquina da bytes distintos y git lo vería como un cambio.
    if destino.exists() and gzip.decompress(destino.read_bytes()) == contenido:
        return
    with open(destino, "wb") as crudo, gzip.GzipFile(fileobj=crudo, mode="wb", mtime=0) as gz:
        gz.write(contenido)


def leer_crudo(ed: ine_eip.Edicion) -> list[ine_eip.Fila]:
    with gzip.open(ruta_crudo(ed), "rt", encoding="utf-8") as gz:
        return [ine_eip.Fila(anyo=ed.anyo, serie=ed.serie, **f) for f in json.load(gz)]


def convertir(cantidad: float | None, desde: str, hasta: str) -> float | None:
    """Pasa una cantidad a la unidad de referencia; None si no son comparables."""
    if cantidad is None or desde == hasta:
        return cantidad
    a, b = A_BASE.get(desde), A_BASE.get(hasta)
    if not a or not b or a[0] != b[0]:
        return None
    return cantidad * a[1] / b[1]


def sumar(valores: list[float | None]) -> float | None:
    presentes = [v for v in valores if v is not None]
    return sum(presentes) if presentes else None


def entero_si_puede(x: float | None):
    if x is None:
        return None
    return int(x) if float(x).is_integer() else round(x, 3)


def alinear_macro(macro: dict, anyos: list[int]) -> dict:
    """Recoloca el PIB y los asalariados sobre los mismos años que los productos."""
    pos = {a: i for i, a in enumerate(macro["anyos"])}

    def serie(valores: list) -> list:
        return [valores[pos[a]] if a in pos else None for a in anyos]

    return {
        "fuente": "INE. Contabilidad Nacional Trimestral (tabla 67821) y EPA (tabla 65988)",
        "pib": serie(macro["pib"]),  # millones de euros
        "asalariados": serie(macro["asalariados"]),  # miles de personas
        "ramas": {
            clave: {"n": r["n"], "vab": serie(r["vab"]), "asalariados": serie(r["asalariados"])}
            for clave, r in macro["ramas"].items()
        },
    }


def construir(filas: list[ine_eip.Fila], macro: dict) -> dict:
    anyos = sorted({f.anyo for f in filas})
    pos = {a: i for i, a in enumerate(anyos)}
    anyos_nueva = [f.anyo for f in filas if f.serie == ine_eip.SERIE_NUEVA]
    hay_antigua = any(f.serie == ine_eip.SERIE_ANTIGUA for f in filas)
    ruptura = min(anyos_nueva) if anyos_nueva and hay_antigua else None

    por_producto: dict[str, list[ine_eip.Fila]] = defaultdict(list)
    for f in filas:
        por_producto[f.prodcom].append(f)

    sectores: dict[str, dict] = {}
    productos = []
    for codigo, grupo in por_producto.items():
        # La ficha (nombre, sector, unidad) es la de la publicación más reciente.
        # y, a ser posible, una que conserve la jerarquía de denominaciones.
        ref = max(grupo, key=lambda f: (f.ruta_completa, f.anyo, f.serie == ine_eip.SERIE_NUEVA))
        celdas: dict[tuple[int, str], list[ine_eip.Fila]] = defaultdict(list)
        for f in grupo:
            celdas[(f.anyo, f.serie)].append(f)

        q: list = [None] * len(anyos)
        v: list = [None] * len(anyos)
        qa = va = None
        for (anyo, serie), mismas in celdas.items():
            cant = sumar([convertir(f.cantidad, f.unidad, ref.unidad) for f in mismas])
            val = sumar([f.valor for f in mismas])
            if anyo == ruptura and serie == ine_eip.SERIE_ANTIGUA:
                qa, va = cant, val  # 2021 según la encuesta antigua: solo para comparar con 2020
                if (anyo, ine_eip.SERIE_NUEVA) in celdas:
                    continue
            q[pos[anyo]], v[pos[anyo]] = entero_si_puede(cant), entero_si_puede(val)

        unidad = unidad_clara(ref.unidad)
        if not unidad:
            q = [None] * len(anyos)  # producto del que solo se publica el valor
            qa = None
        producto = {
            "c": codigo, "s": ref.sector, "e": emoji_de(ref.ruta, ref.sector),
            "n": nombre_de(codigo, ref.ruta), "o": ref.ruta, "u": unidad, "q": q, "v": v,
        }
        if qa is not None:
            producto["qa"] = entero_si_puede(qa)
        if va is not None:
            producto["va"] = entero_si_puede(va)
        productos.append(producto)

        emoji, corto = SECTORES.get(ref.sector, ("🏭", ref.sector_nombre))
        sectores.setdefault(
            ref.sector,
            {"n": corto, "o": ref.sector_nombre, "e": emoji, "cnae": ref.cnae,
             "r": ine_macro.rama_de(ref.cnae)},
        )

    productos.sort(key=lambda p: p["c"])
    return {
        "meta": {
            "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fuente": "INE. Encuesta Industrial Anual de Productos",
            "url": ine_eip.URL_RESULTADOS,
            "anyos": anyos,
            "ultimo": anyos[-1],
            "ruptura": ruptura,
            "unidad_valor": "miles de euros",
        },
        "macro": alinear_macro(macro, anyos),
        "sectores": dict(sorted(sectores.items())),
        "productos": productos,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anyos", type=int, nargs="+", metavar="AAAA",
                    help="descargar solo estos años; el resto se lee de data/crudo/")
    ap.add_argument("--sin-descarga", action="store_true",
                    help="no conectar con el INE: regenerar el JSON desde data/crudo/")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if args.sin_descarga:
        ediciones = []
        for fichero in sorted(CRUDO.glob("*.json.gz")):
            anyo, serie = fichero.name.removesuffix(".json.gz").split("-")
            ediciones.append(ine_eip.Edicion(int(anyo), serie, ""))
        a_descargar: list[ine_eip.Edicion] = []
    else:
        print("Consultando en el INE los años publicados…")
        ediciones = ine_eip.listar_ediciones()
        a_descargar = [
            e for e in ediciones
            if not args.anyos or e.anyo in args.anyos or not ruta_crudo(e).exists()
        ]
    if not ediciones:
        print("No hay datos: ejecuta el script sin --sin-descarga.", file=sys.stderr)
        return 1

    inicio = time.time()
    if a_descargar:
        print(f"Descargando {len(a_descargar)} publicaciones "
              f"({', '.join(str(e.anyo) for e in a_descargar)}). Tarda varios minutos…")
        with cf.ThreadPoolExecutor(HILOS) as pool:
            tareas = {pool.submit(ine_eip.descargar_edicion, e): e for e in a_descargar}
            for tarea in cf.as_completed(tareas):
                ed = tareas[tarea]
                filas = tarea.result()  # si un año falla, se aborta sin tocar lo publicado
                if len(filas) < MIN_PRODUCTOS:
                    raise RuntimeError(f"{ed.anyo} ({ed.serie}): solo {len(filas)} productos; descarga incompleta")
                guardar_crudo(ed, filas)
                print(f"  ✓ {ed.anyo} ({ed.serie}): {len(filas)} productos  [{time.time() - inicio:.0f} s]")

    if not args.sin_descarga:
        print("Descargando PIB y asalariados…")
        macro = ine_macro.descargar()
        contenido = json.dumps(macro, ensure_ascii=False, indent=1).encode("utf-8")
        CRUDO.mkdir(parents=True, exist_ok=True)
        if not CRUDO_MACRO.exists() or CRUDO_MACRO.read_bytes() != contenido:
            CRUDO_MACRO.write_bytes(contenido)
    macro = json.loads(CRUDO_MACRO.read_text(encoding="utf-8"))

    filas = [f for e in ediciones for f in leer_crudo(e)]
    datos = construir(filas, macro)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    temporal = SALIDA.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporal.replace(SALIDA)

    # La página «Producción final» (final.html) clasifica estos mismos productos.
    if not args.sin_descarga:
        print("Descargando las tablas input-output…")
    produccion_final.generar(datos, descargar=not args.sin_descarga)

    meta = datos["meta"]
    print(f"Listo: {len(datos['productos'])} productos, {meta['anyos'][0]}–{meta['ultimo']} "
          f"→ {SALIDA.relative_to(RAIZ)} ({SALIDA.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
