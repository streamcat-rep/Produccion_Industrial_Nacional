"""A qué producción final va cada producto industrial. **Edítalo para reclasificar.**

El PIB solo cuenta la producción final: una lata de conservas no es producción
final, lo es la conserva que la lleva dentro. Aquí se decide, producto a
producto, si es un bien final o un insumo y a qué grupo de producción final
pertenece. Tres capas, de la más oficial a la más artesanal:

1. ETAPA: los «grandes sectores industriales» de la UE (Reglamento (CE) 656/2007),
   que asignan cada grupo de la CNAE a consumo, equipo, intermedios o energía.
2. REGLAS: por prefijo del código PRODCOM (gana el más largo). Un producto puede ser
     ("final", grupo)        bien final: todo su valor va a ese grupo.
     ("usuarios", [CNAE…])   insumo de esas ramas: se reparte como lo que ellas producen.
     ("io",)                 insumo genérico: se reparte según quién lo compra en la
                             tabla input-output del INE.
     ("energia",)            energía: parte se consume directamente y parte es insumo.
3. Sin regla, decide la etapa: los intermedios son ("io",), la energía ("energia",)
   y un bien de consumo o de equipo debe tener regla "final" (si falta, el
   script falla en vez de inventarse el grupo).
"""
from __future__ import annotations

# --- Grupos de producción final ---------------------------------------------------
# (id, emoji, nombre, qué incluye)
GRUPOS: list[tuple[str, str, str, str]] = [
    ("ALIM", "🍽️", "Alimentación, bebidas y tabaco",
     "Alimentos, bebidas y tabaco, con el campo, la pesca y sus envases"),
    ("VEST", "👕", "Vestido, calzado y adorno personal",
     "Ropa, calzado, marroquinería y joyería, con sus hilados, tejidos y cueros"),
    ("VIV", "🏠", "Vivienda y construcción",
     "Edificios y obra civil, con el cemento, el ladrillo, el azulejo o la carpintería que llevan"),
    ("HOGAR", "🛋️", "Equipamiento del hogar",
     "Muebles, electrodomésticos, textil del hogar, menaje y otros artículos de uso doméstico"),
    ("SALUD", "💊", "Salud, higiene y cuidados",
     "Medicamentos, material sanitario, sanidad y servicios sociales, limpieza, cosmética y papel higiénico"),
    ("TRANS", "🚗", "Vehículos y transporte",
     "Automóviles, trenes, barcos, aviones y los servicios de transporte, con sus piezas y neumáticos"),
    ("ENER", "⚡", "Energía, agua y residuos",
     "Electricidad, gas, combustibles, agua y gestión de residuos que llegan al consumo final"),
    ("CULT", "📱", "Electrónica, información, cultura y ocio",
     "Electrónica, telecomunicaciones, edición, audiovisual, deporte, juguetes y espectáculos"),
    ("EQUIPO", "⚙️", "Maquinaria y bienes de equipo",
     "Máquinas, equipo eléctrico e instalaciones con las que se produce (inversión)"),
    ("COM", "🛒", "Comercio y distribución",
     "El servicio de comercio mayorista y minorista (sus márgenes), con lo que gasta para prestarlo"),
    ("HOST", "🍴", "Hostelería y turismo",
     "Alojamiento, restauración y agencias de viajes"),
    ("PUB", "🏛️", "Administración, educación y defensa",
     "Administración pública, educación, defensa y servicios colectivos"),
    ("EMP", "💼", "Finanzas y servicios profesionales",
     "Banca, seguros y servicios profesionales que llegan a la demanda final"),
    ("EXPI", "🚢", "Materiales exportados",
     "Bienes intermedios que salen de España como tales: son insumo de la producción de otros países"),
]

# --- Etapa oficial (Main Industrial Groupings, Reglamento (CE) 656/2007) --------------
ETAPAS = {
    "CN": "Consumo no duradero",
    "CD": "Consumo duradero",
    "EQ": "Bienes de equipo",
    "IN": "Bienes intermedios",
    "EN": "Energía",
}
# Por división (2 dígitos) o grupo (3 dígitos) de la CNAE; el grupo manda sobre la división.
MIG = {
    "IN": "07 08 09 106 109 131 132 133 16 17 201 202 203 205 206 22 23 24 255 256 257 259 "
          "261 268 271 272 273 274 279",
    "EN": "05 06 19 35 36",
    "EQ": "251 252 253 254 262 263 265 266 28 29 301 302 303 304 325 33",
    "CD": "264 267 275 309 31 321 322",
    "CN": "101 102 103 104 105 107 108 11 12 139 14 15 18 204 21 323 324 329",
}
_ETAPA_DE = {codigo: etapa for etapa, codigos in MIG.items() for codigo in codigos.split()}


def etapa_de(prodcom: str) -> str:
    for n in (3, 2):
        if prodcom[:n] in _ETAPA_DE:
            return _ETAPA_DE[prodcom[:n]]
    raise KeyError(f"El producto {prodcom} no encaja en ningún gran sector industrial")


# --- Tabla input-output: 64 productos de la CPA -----------------------------------
# Divisiones de la CNAE/CPA que cubre cada producto de la tabla, en su orden.
TIO_DIVISIONES = (
    "01 02 03 05-09 10-12 13-15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31-32 33 35 36 "
    "37-39 41-43 45 46 47 49 50 51 52 53 55-56 58 59-60 61 62-63 64 65 66 68 69-70 71 72 73 "
    "74-75 77 78 79 80-82 84 85 86 87-88 90-92 93 94 95 96 97-98 99"
).split()

# Grupo final al que va la demanda final interior (consumo + inversión) de cada división.
_FINAL_INTERIOR = {
    "ALIM": "01 03 10-12",
    "VEST": "13-15",
    "VIV": "02 16 41-43 68",
    "HOGAR": "22 23 31-32 95 97-98",
    "SALUD": "17 20 21 86 87-88 96",
    "TRANS": "29 30 45 49 50 51 52 53",
    "ENER": "05-09 19 35 36 37-39",
    "CULT": "18 26 58 59-60 61 62-63 90-92 93",
    "EQUIPO": "24 25 27 28 33",
    "COM": "46 47",
    "HOST": "55-56 79",
    "PUB": "84 85 94 99",
    "EMP": "64 65 66 69-70 71 72 73 74-75 77 78 80-82",
}
# Ramas cuyo producto se exporta sobre todo como material para otros: su exportación
# no termina en un bien final español, sino en la producción de otro país.
_EXPORTA_MATERIALES = "02 05-09 16 17 20 22 23 24".split()

FINAL_INTERIOR = {div: grupo for grupo, divs in _FINAL_INTERIOR.items() for div in divs.split()}
FINAL_EXPORTADO = {div: ("EXPI" if div in _EXPORTA_MATERIALES else g) for div, g in FINAL_INTERIOR.items()}


def rama_tio(division: str) -> int:
    """Posición en la tabla input-output de una división CNAE ('25' -> 15)."""
    d = int(division)
    for i, tramo in enumerate(TIO_DIVISIONES):
        ini, _, fin = tramo.partition("-")
        if int(ini) <= d <= int(fin or ini):
            return i
    raise KeyError(f"La división {division} no está en la tabla input-output")


# --- Reglas por prefijo PRODCOM ------------------------------------------------------
F, U = "final", "usuarios"
AGRO, ALIMENTARIA, CONSTRUCCION, AUTOMOCION = ["01"], ["10"], ["41"], ["29"]
ENVASADORES = ["10", "20", "21"]  # alimentación y bebidas, química y cosmética, farmacia
# Embalaje general: lo usa quien fabrica o mueve mercancías.
MERCANCIAS = ["01", "03", "10", "13", "16", "17", "20", "21", "22", "23", "24", "25", "26",
              "27", "28", "29", "31", "45", "46", "47", "49", "52", "53"]

REGLAS: dict[str, tuple] = {
    # Alimentación, bebidas y tabaco
    "10": (F, "ALIM"), "11": (F, "ALIM"), "12": (F, "ALIM"),
    "106": (U, ALIMENTARIA),        # harinas, arroz, almidones: ingrediente de otros alimentos
    "1091": (U, AGRO),              # piensos para la ganadería
    "1092": (F, "HOGAR"),           # comida para mascotas
    "1106": (U, ALIMENTARIA),       # malta
    # Textil, confección, cuero y calzado
    "1391": ("io",),                # tejidos de punto en pieza
    "1392": (F, "HOGAR"),           # ropa de cama, cortinas, toldos, bayetas
    "139221": (U, MERCANCIAS),      # sacos y talegas para envasar
    "1393": (F, "HOGAR"),           # alfombras
    "1394": ("io",), "1395": ("io",), "1396": ("io",), "1399": ("io",),  # cuerdas, telas técnicas
    "14": (F, "VEST"), "15": (F, "VEST"),
    "1511": ("io",),                # curtido: cuero para calzado, marroquinería, tapicerías
    # Madera y papel
    "1622": (U, CONSTRUCCION), "1623": (U, CONSTRUCCION),  # parqué, puertas, ventanas
    "1624": (U, MERCANCIAS),        # palets y envases de madera
    "1721": (U, MERCANCIAS),        # cartón ondulado, cajas y bolsas de papel
    "1722": (F, "SALUD"),           # papel higiénico, pañales, compresas, servilletas
    "1723": (F, "CULT"),            # artículos de papelería
    "1724": (F, "HOGAR"),           # papel pintado
    "172911": (U, MERCANCIAS),      # etiquetas
    "18": ("io",),                  # la impresión se hace casi toda por encargo de otras empresas
    # Química y farmacia
    "2015": (U, AGRO), "202": (U, AGRO),  # abonos y fitosanitarios
    "204": (F, "SALUD"),            # jabones, detergentes, perfumes y cosmética
    "21": (F, "SALUD"),
    "211": (U, ["21"]),             # principios activos: insumo de los medicamentos
    # Caucho y plástico
    "2211": (F, "TRANS"),           # neumáticos
    "2222": (U, ENVASADORES + ["01", "46", "47"]),  # bolsas, cajas, botellas y tapones de plástico
    "2223": (U, CONSTRUCCION),      # plástico para la construcción
    "222923": (F, "HOGAR"),         # vajilla y artículos domésticos de plástico
    "2229916": (U, AUTOMOCION),     # piezas de plástico para automóviles
    # Vidrio, cerámica y materiales de construcción
    "231311": (U, ALIMENTARIA),     # tarros y botellas de vidrio
    "23131170": (U, ["21"]),        # frascos para farmacia
    "23131180": (U, ENVASADORES),   # otros recipientes de vidrio
    "231312": (F, "HOGAR"), "231313": (F, "HOGAR"),  # vasos y servicio de mesa
    "233": (U, CONSTRUCCION),       # azulejos, ladrillos y tejas
    "2341": (F, "HOGAR"),           # vajillas y adornos de cerámica
    "2342": (U, CONSTRUCCION),      # sanitarios
    "235": (U, CONSTRUCCION), "236": (U, CONSTRUCCION), "237": (U, CONSTRUCCION),  # cemento, hormigón, piedra
    # Productos metálicos
    "251": (U, CONSTRUCCION),       # estructuras, puertas y ventanas metálicas
    "2521": (U, CONSTRUCCION),      # radiadores y calderas de calefacción
    "2529": (F, "EQUIPO"), "253": (F, "EQUIPO"),  # depósitos y generadores de vapor
    "254": (F, "PUB"),              # armas y municiones
    "2571": (F, "HOGAR"),           # cuchillería y cubertería
    "2572": (U, CONSTRUCCION),      # cerraduras y herrajes
    "2573": (F, "EQUIPO"),          # herramientas
    "259211": (U, ALIMENTARIA),     # latas de conserva
    "259212": (U, ENVASADORES),     # latas de bebida, tubos y aerosoles de aluminio
    "259213": (U, ALIMENTARIA),     # tapones corona, cápsulas y tapas
    "259911": (F, "HOGAR"), "259912": (F, "HOGAR"),  # fregaderos, baterías de cocina, menaje
    # Electrónica, material eléctrico y maquinaria
    "262": (F, "CULT"), "263": (F, "CULT"), "264": (F, "CULT"), "267": (F, "CULT"),
    "265": (F, "EQUIPO"),
    "2652": (F, "VEST"),            # relojes
    "266": (F, "SALUD"),            # equipos electromédicos
    "275": (F, "HOGAR"),            # electrodomésticos
    "28": (F, "EQUIPO"),
    # Material de transporte
    "291": (F, "TRANS"), "292": (F, "TRANS"),
    "293": (U, AUTOMOCION),         # componentes de automoción
    "30": (F, "TRANS"),
    "3012": (F, "CULT"),            # embarcaciones de recreo
    # Muebles y otras manufacturas
    "31": (F, "HOGAR"),
    "3101": (F, "EQUIPO"),          # muebles de oficina y de comercio
    "3211": (F, "PUB"),             # monedas
    "3212": (F, "VEST"), "3213": (F, "VEST"),  # joyería y bisutería
    "322": (F, "CULT"), "323": (F, "CULT"), "324": (F, "CULT"),  # música, deporte, juegos
    "325": (F, "SALUD"),            # instrumental médico, ortopedia y prótesis
    "329": (F, "HOGAR"),
    # Reparación e instalación
    "331": ("io",),                 # reparar máquinas es un gasto corriente de quien las usa
    "332": (F, "EQUIPO"),           # instalarlas es inversión
}

# Piezas hechas para un cliente concreto: la denominación lo dice aunque el código no.
PALABRAS: list[tuple[str, tuple]] = [
    ("vehículos automóviles", (U, AUTOMOCION)),
    ("para automóviles", (U, AUTOMOCION)),
]


def regla_de(prodcom: str, ruta: list[str]) -> tuple:
    """Regla que se aplica a un producto: la del prefijo más largo, o la de su etapa."""
    etapa = etapa_de(prodcom)
    for n in range(len(prodcom), 1, -1):
        if prodcom[:n] in REGLAS:
            regla = REGLAS[prodcom[:n]]
            break
    else:
        regla = {"IN": ("io",), "EN": ("energia",)}.get(etapa)
        if regla is None:
            raise KeyError(f"El producto final {prodcom} ({' > '.join(ruta)}) no tiene grupo asignado")
    if regla[0] != F:
        texto = " ".join(ruta).lower()
        for palabra, especial in PALABRAS:
            if palabra in texto:
                return especial
    return regla
