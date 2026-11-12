#!/usr/bin/env python3
"""Genera data/final.json: a qué producción final va cada producto industrial.

Uso:
    python scripts/produccion_final.py                 # descarga las tablas input-output del INE
    python scripts/produccion_final.py --sin-descarga  # las lee de data/crudo/ (p. ej. tras tocar destinos.py)

La suma de la Encuesta Industrial cuenta varias veces lo mismo: la lata, y otra
vez dentro de la conserva. El PIB solo cuenta la producción final. Este script
dice, para cada producto, si es final o insumo y en qué grupo de producción
final acaba su valor (scripts/destinos.py tiene las reglas).

Los insumos se reparten con la tabla input-output interior del INE. Si A son los
coeficientes técnicos y f la demanda final, la producción es x = L·f con
L = (I − A)⁻¹ (inversa de Leontief), de modo que L[i][j]·f[j] es la producción de
la rama i que termina dentro del producto final j. Dos repartos salen de ahí:

  - «usuarios»: el insumo lo compra un conjunto de ramas K (las latas de conserva,
    la industria alimentaria). Se pondera cada rama k de K por lo que compra de ese
    tipo de producto (z[i][k]) y se reparte como la producción de k: L[k][j]·f[j].
  - «io»: insumo genérico. Se reparte como la producción intermedia de su rama,
    (L − I)[i][j]·f[j], más la parte que se exporta directamente.

Cada año de la encuesta usa la tabla input-output del año más cercano.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import destinos
import ine_tio

RAIZ = Path(__file__).resolve().parent.parent
PRODUCCION = RAIZ / "data" / "produccion.json"
SALIDA = RAIZ / "data" / "final.json"
CRUDO_TIO = RAIZ / "data" / "crudo" / "input-output" / "tablas.json.gz"
GRUPOS = [g[0] for g in destinos.GRUPOS]
N = ine_tio.RAMAS


def guardar_crudo(tablas: dict) -> None:
    contenido = json.dumps(tablas, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if CRUDO_TIO.exists() and gzip.decompress(CRUDO_TIO.read_bytes()) == contenido:
        return  # mismo contenido: no reescribir, para que git no vea un cambio
    CRUDO_TIO.parent.mkdir(parents=True, exist_ok=True)
    with open(CRUDO_TIO, "wb") as crudo, gzip.GzipFile(fileobj=crudo, mode="wb", mtime=0) as gz:
        gz.write(contenido)


def leer_crudo() -> dict:
    with gzip.open(CRUDO_TIO, "rt", encoding="utf-8") as gz:
        return json.load(gz)


def inversa(m: list[list[float]]) -> list[list[float]]:
    """Inversa por Gauss-Jordan con pivote parcial."""
    n = len(m)
    a = [fila[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, fila in enumerate(m)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(a[r][c]))
        if abs(a[p][c]) < 1e-12:
            raise RuntimeError("La matriz (I − A) de la tabla input-output no es invertible")
        a[c], a[p] = a[p], a[c]
        pivote = a[c][c]
        a[c] = [v / pivote for v in a[c]]
        for r in range(n):
            if r != c and a[r][c]:
                factor = a[r][c]
                a[r] = [v - factor * w for v, w in zip(a[r], a[c])]
    return [fila[n:] for fila in a]


class Modelo:
    """Una tabla input-output lista para repartir producción entre grupos finales."""

    def __init__(self, tabla: dict):
        self.z, self.x, self.export = tabla["z"], tabla["x"], tabla["export"]
        interior = [c + k for c, k in zip(tabla["consumo"], tabla["capital"])]
        coef = [[self.z[i][k] / self.x[k] if self.x[k] > 0 else 0.0 for k in range(N)] for i in range(N)]
        self.leontief = inversa([[(i == k) - coef[i][k] for k in range(N)] for i in range(N)])
        # Comprobación: la inversa reproduce la producción, x = L·f.
        for i in range(N):
            x = sum(self.leontief[i][j] * (interior[j] + self.export[j]) for j in range(N))
            if abs(x - self.x[i]) > max(1.0, 1e-6 * abs(self.x[i])):
                raise RuntimeError(f"La inversa de Leontief no reproduce la producción de la rama {i + 1}")
        g_int = [GRUPOS.index(destinos.FINAL_INTERIOR[d]) for d in destinos.TIO_DIVISIONES]
        g_exp = [GRUPOS.index(destinos.FINAL_EXPORTADO[d]) for d in destinos.TIO_DIVISIONES]
        # incorporado[i][g]: producción de la rama i que acaba en bienes finales del grupo g.
        self.incorporado = [[0.0] * len(GRUPOS) for _ in range(N)]
        # intermedio[i][g]: lo mismo, pero solo la parte que se vende como insumo.
        self.intermedio = [[0.0] * len(GRUPOS) for _ in range(N)]
        for i in range(N):
            for j in range(N):
                for demanda, grupo in ((interior[j], g_int[j]), (self.export[j], g_exp[j])):
                    self.incorporado[i][grupo] += self.leontief[i][j] * demanda
                    self.intermedio[i][grupo] += (self.leontief[i][j] - (i == j)) * demanda

    @staticmethod
    def _cuotas(pesos: list[float]) -> list[float]:
        # Una variación de existencias negativa puede dar algún peso negativo: se ignora.
        pesos = [max(p, 0.0) for p in pesos]
        total = sum(pesos)
        if total <= 0:
            raise RuntimeError("Reparto sin destino: la tabla input-output no da ningún uso")
        return [round(p / total, 4) for p in pesos]

    def energia(self, rama: int) -> list[float]:
        return self._cuotas(self.incorporado[rama])

    def generico(self, rama: int, cuota_insumos: float) -> list[float]:
        pesos = self.intermedio[rama][:]
        # Los insumos de la rama también se exportan tal cual, en proporción a lo que pesan en ella.
        pesos[GRUPOS.index("EXPI")] += cuota_insumos * max(self.export[rama], 0.0)
        return self._cuotas(pesos)

    def usuarios(self, rama: int, compradoras: list[int]) -> list[float]:
        compras = [max(self.z[rama][k], 0.0) for k in compradoras]
        if sum(compras) <= 0:
            compras = [1.0] * len(compradoras)
        pesos = [0.0] * len(GRUPOS)
        for k, compra in zip(compradoras, compras):
            destino = self._cuotas(self.incorporado[k])
            for g, cuota in enumerate(destino):
                pesos[g] += compra * cuota
        return self._cuotas(pesos)


def clasificar(productos: list[dict]) -> dict[str, tuple[str, str, tuple]]:
    """Código PRODCOM -> (etapa, id de regla, regla)."""
    fichas = {}
    for p in productos:
        codigo = p["c"]
        regla = destinos.regla_de(codigo, p["o"])
        rama = destinos.rama_tio(codigo[:2])
        if regla[0] == "final":
            if regla[1] not in GRUPOS:
                raise KeyError(f"Grupo desconocido en destinos.py: {regla[1]}")
            rid = f"f:{regla[1]}"
        elif regla[0] == "usuarios":
            rid = f"u:{rama}:{'+'.join(regla[1])}"
        elif regla[0] == "io":
            rid = f"io:{rama}"
        elif regla[0] == "energia":
            rid = f"en:{rama}"
        else:
            raise KeyError(f"Regla desconocida en destinos.py: {regla}")
        fichas[codigo] = (destinos.etapa_de(codigo), rid, regla)
    return fichas


def construir(datos: dict, tablas: dict) -> dict:
    anyos = datos["meta"]["anyos"]
    productos = datos["productos"]
    fichas = clasificar(productos)
    modelos = {int(a): Modelo(t) for a, t in tablas.items()}
    nombres_tio = tablas[max(tablas, key=int)]["nombres"]
    # Año de la encuesta -> año de la tabla input-output más cercana.
    tio_de = {a: min(modelos, key=lambda t: (abs(t - a), -t)) for a in anyos}

    # Peso de los insumos genéricos en la producción de su rama, cada año.
    genericos = [defaultdict(float) for _ in anyos]
    totales = [defaultdict(float) for _ in anyos]
    for p in productos:
        rama = destinos.rama_tio(p["c"][:2])
        for n, valor in enumerate(p["v"]):
            if valor:
                totales[n][rama] += valor
                if fichas[p["c"]][2][0] == "io":
                    genericos[n][rama] += valor

    reglas, perfiles = {}, {}
    for _etapa, rid, regla in fichas.values():
        if rid in reglas:
            continue
        tipo = regla[0]
        if tipo == "final":
            reglas[rid] = {"t": "final", "g": regla[1]}
            continue
        rama = int(rid.split(":")[1])
        ficha = {"t": tipo, "r": nombres_tio[rama]}
        compradoras: list[int] = []
        if tipo == "usuarios":
            compradoras = sorted({destinos.rama_tio(d) for d in regla[1]})
            ficha["k"] = [nombres_tio[k] for k in compradoras]
        reglas[rid] = ficha
        perfil = []
        for n, anyo in enumerate(anyos):
            modelo = modelos[tio_de[anyo]]
            if tipo == "usuarios":
                perfil.append(modelo.usuarios(rama, compradoras))
            elif tipo == "energia":
                perfil.append(modelo.energia(rama))
            else:
                cuota = genericos[n][rama] / totales[n][rama] if totales[n][rama] else 0.0
                perfil.append(modelo.generico(rama, cuota))
        perfiles[rid] = perfil

    return {
        "meta": {
            "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fuente": "INE. Contabilidad Nacional Anual de España: tablas input-output (producción interior)",
            "url": ine_tio.URL_RESULTADOS,
            "anyos": anyos,
            "tio": [tio_de[a] for a in anyos],
        },
        "grupos": [{"id": i, "e": e, "n": n, "d": d} for i, e, n, d in destinos.GRUPOS],
        "etapas": destinos.ETAPAS,
        "reglas": dict(sorted(reglas.items())),
        "perfiles": dict(sorted(perfiles.items())),
        "productos": {c: [etapa, rid] for c, (etapa, rid, _) in sorted(fichas.items())},
    }


def generar(datos: dict, descargar: bool) -> dict:
    """Escribe data/final.json a partir del contenido de produccion.json."""
    if descargar:
        guardar_crudo(ine_tio.descargar())
    if not CRUDO_TIO.exists():
        raise RuntimeError("Faltan las tablas input-output: ejecuta el script sin --sin-descarga")
    final = construir(datos, leer_crudo())
    temporal = SALIDA.with_suffix(".tmp")
    temporal.write_text(json.dumps(final, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporal.replace(SALIDA)
    return final


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sin-descarga", action="store_true",
                    help="no conectar con el INE: usar las tablas guardadas en data/crudo/")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    datos = json.loads(PRODUCCION.read_text(encoding="utf-8"))
    final = generar(datos, descargar=not args.sin_descarga)
    tipos = defaultdict(int)
    for _, rid in final["productos"].values():
        tipos[final["reglas"][rid]["t"]] += 1
    print(f"Listo: {len(final['productos'])} productos ({dict(tipos)}), tablas input-output de "
          f"{sorted(set(final['meta']['tio']))} → {SALIDA.relative_to(RAIZ)} ({SALIDA.stat().st_size / 1e3:.0f} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
