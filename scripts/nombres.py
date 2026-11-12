"""Nombres claros, emojis y unidades legibles para los productos de la EIAP.

El INE publica cada producto como una hoja dentro de una jerarquía, de modo que
la hoja sola no se entiende ("Despiezada", "Las demás"). Aquí se reconstruye una
frase completa a partir de la jerarquía y se le asigna un emoji por palabras
clave (o, si ninguna encaja, el de su sector).
"""
from __future__ import annotations

import re
import unicodedata

# Sector EIAP -> (emoji, nombre corto). El nombre oficial se conserva aparte.
SECTORES: dict[str, tuple[str, str]] = {
    "01": ("⛏️", "Minería y extracción"),
    "02": ("⛏️", "Minería y extracción"),
    "03": ("🥩", "Cárnicas"),
    "04": ("🐟", "Pescado y conservas de pescado"),
    "05": ("🥫", "Frutas y hortalizas preparadas"),
    "06": ("🫒", "Aceites y grasas"),
    "07": ("🥛", "Lácteos"),
    "08": ("🌾", "Harinas, molinería y almidones"),
    "09": ("🥖", "Pan, galletas y pastelería"),
    "10": ("🍚", "Azúcar"),
    "11": ("🍫", "Cacao, chocolate y confitería"),
    "12": ("🍲", "Otros alimentos"),
    "13": ("🐄", "Piensos y alimentación animal"),
    "14": ("🥃", "Destilados y alcohol"),
    "15": ("🍷", "Vino"),
    "16": ("🍏", "Sidra y otras bebidas fermentadas"),
    "17": ("🍺", "Cerveza y malta"),
    "18": ("🥤", "Aguas y refrescos"),
    "19": ("🚬", "Tabaco"),
    "20": ("🧵", "Hilados y tejidos"),
    "21": ("🎨", "Acabado de textiles"),
    "22": ("🛏️", "Artículos textiles (no ropa)"),
    "23": ("🧶", "Alfombras y otros textiles"),
    "24": ("🧦", "Tejidos y prendas de punto"),
    "25": ("👕", "Ropa y confección"),
    "26": ("🐂", "Curtido de cuero"),
    "27": ("👜", "Marroquinería"),
    "28": ("👞", "Calzado"),
    "29": ("🪵", "Madera aserrada"),
    "30": ("🪚", "Productos de madera y corcho"),
    "31": ("📜", "Pasta de papel, papel y cartón"),
    "32": ("📦", "Artículos de papel y cartón"),
    "33": ("🖨️", "Artes gráficas e impresión"),
    "34": ("⚗️", "Química inorgánica básica"),
    "35": ("🎨", "Colorantes y pigmentos"),
    "36": ("🧪", "Química orgánica básica"),
    "37": ("🌱", "Abonos y agroquímicos"),
    "38": ("♻️", "Plásticos y caucho en bruto"),
    "39": ("🖌️", "Pinturas, barnices y tintas"),
    "40": ("🧼", "Limpieza, perfumería y cosmética"),
    "41": ("🧪", "Otros productos químicos"),
    "42": ("🧵", "Fibras artificiales y sintéticas"),
    "43": ("💊", "Farmacia"),
    "44": ("🛞", "Productos de caucho"),
    "45": ("🧴", "Productos de plástico"),
    "46": ("🪟", "Vidrio"),
    "47": ("🏺", "Cerámica y refractarios"),
    "48": ("🧱", "Azulejos, ladrillos y tejas"),
    "49": ("🏗️", "Cemento, hormigón, cal y yeso"),
    "50": ("🪨", "Piedra y minerales no metálicos"),
    "51": ("🔩", "Hierro y acero"),
    "52": ("🥇", "Metales preciosos y no férreos"),
    "53": ("🔥", "Fundición de metales"),
    "54": ("🏢", "Estructuras metálicas, depósitos y calderas"),
    "55": ("🔨", "Forja, estampación y tratamiento de metales"),
    "56": ("🔧", "Herramientas, cuchillería y herrajes"),
    "57": ("🔩", "Armas y otros productos metálicos"),
    "58": ("💻", "Informática y electrónica"),
    "59": ("⏱️", "Instrumentos de medida y relojes"),
    "60": ("🔬", "Equipos médicos, ópticos y fotográficos"),
    "61": ("⚡", "Maquinaria y material eléctrico"),
    "62": ("🧺", "Electrodomésticos"),
    "63": ("⚙️", "Maquinaria de uso general"),
    "64": ("🛠️", "Máquinas-herramienta"),
    "65": ("🚜", "Tractores y maquinaria agrícola"),
    "66": ("🏭", "Maquinaria para usos específicos"),
    "67": ("🚗", "Automóviles y componentes"),
    "68": ("🚢", "Construcción naval"),
    "69": ("🚆", "Material ferroviario"),
    "70": ("✈️", "Aeronáutica y espacio"),
    "71": ("🏍️", "Motos, bicicletas y otro transporte"),
    "72": ("🪑", "Muebles"),
    "73": ("💍", "Joyería, monedas y bisutería"),
    "74": ("🎸", "Instrumentos musicales"),
    "75": ("🧸", "Deporte, juegos y juguetes"),
    "76": ("🩺", "Material médico y dental"),
    "77": ("🧹", "Otras manufacturas"),
    "78": ("🧰", "Reparación e instalación de maquinaria"),
    "79": ("💡", "Electricidad, gas y vapor"),
    "80": ("🪨", "Coquerías"),
    "81": ("🛢️", "Refino de petróleo"),
}

# Unidad tal y como la escribe el INE -> texto legible. "" = solo se publica el valor.
UNIDADES: dict[str, str] = {
    "---": "",
    "........": "",
    "t.": "toneladas",
    "kg": "kilogramos",
    "gramo": "gramos",
    "Unidades": "unidades",
    "mil unidades": "miles de unidades",
    "Pares": "pares",
    "mil pares": "miles de pares",
    "m.": "metros",
    "mil metros": "miles de metros",
    "m2": "metros cuadrados",
    "mil m2": "miles de metros cuadrados",
    "m3": "metros cúbicos",
    "mil m3": "miles de metros cúbicos",
    "Litros": "litros",
    "mil litros": "miles de litros",
    "hectolitro": "hectolitros",
    "hl. alc. 100%": "hectolitros de alcohol puro",
    "l. alc. 100%": "litros de alcohol puro",
    "1.000 kWh": "MWh (miles de kWh)",
    "Kw": "kilovatios de potencia",
    "terajulios": "terajulios",
    "CGT": "toneladas brutas compensadas (CGT)",
    "Nº celdas": "número de celdas",
    "kg. act. sub": "kg de sustancia activa",
    "t. 90% s.d.t.": "toneladas al 90 % de materia seca",
    "quilates": "quilates",
}
_SUSTANCIA = re.compile(r"^(t|kg)\.\s+(.+)$")  # "t. N", "kg. TiO2": peso del compuesto puro


def unidad_clara(unidad: str) -> str:
    unidad = unidad.strip()
    if unidad in UNIDADES:
        return UNIDADES[unidad]
    m = _SUSTANCIA.match(unidad)
    if m:
        peso = "toneladas" if m.group(1) == "t" else "kg"
        return f"{peso} de {m.group(2)}"
    return unidad


# --- Nombre claro ------------------------------------------------------------

_ABREVIATURAS = [
    # referencias internas del cuestionario del INE, que no aportan nada al lector
    (r"\s*\bSector(?:es)?\s?\d+(?:\s*(?:,|y)\s*\d+)*", ""),
    (r",?\s*\bMod\.\s?\d+\s+c[oó]d\.\s?[\d-]+", ""),
    (r"\s*\(1\)\s*$", ""),
    (r"\bn\.\s?c\.\s?o\.\s?p\.?", "no clasificados en otra parte"),
    (r"\bn\.\s?c\.\s?p\.?", "no clasificados en otra parte"),
    (r"\bexc\.\s", "excepto "),
    (r"\bincl\.\s", "incluido "),
    (r"\bp\.\s?ej\.", "por ejemplo"),
    (r"\betc\b\.?", "etc."),
    (r">\s?=", "≥"),
    (r"<\s?=", "≤"),
    (r"\bm2\b", "m²"),
    (r"\bm3\b", "m³"),
    (r"\bcm2\b", "cm²"),
    (r"\bcm3\b", "cm³"),
]
# Hojas que por sí solas no dicen nada: "las demás" de qué.
_RESTO = re.compile(
    r"^(l[oa]s\s+dem[aá]s|otr[oa]s?|l[oa]s\s+otr[oa]s|el\s+resto|resto|dem[aá]s)\b\.?", re.I
)


def _limpiar(texto: str) -> str:
    for patron, cambio in _ABREVIATURAS:
        texto = re.sub(patron, cambio, texto, flags=re.I)
    return re.sub(r"\s+", " ", texto).strip(" .;:,")


def _minuscula_inicial(texto: str) -> str:
    """Baja la primera letra salvo que sea una sigla (PVC, ABS, TV...)."""
    if len(texto) > 1 and texto[1].isupper():
        return texto
    return texto[:1].lower() + texto[1:]


def nombre_claro(ruta: list[str]) -> str:
    """['Carnes', 'Frescas o refrigeradas', 'De bovino', 'Despiezada']
    -> 'Carnes frescas o refrigeradas de bovino: despiezada'."""
    niveles = [_limpiar(n) for n in ruta if n and n.strip()]
    if not niveles:
        return "Producto sin denominación"
    if len(niveles) == 1:
        return niveles[0][:1].upper() + niveles[0][1:]
    *padres, hoja = niveles
    contexto = padres[0] + "".join(" " + _minuscula_inicial(p) for p in padres[1:])
    resto = _RESTO.match(hoja)
    cola = hoja[resto.end():].strip() if resto else ""
    if resto and (not cola or cola.startswith("(")):
        # "Las demás (excepto X)" -> "otros tipos (excepto X)"; "Otras piezas" se queda igual
        hoja = "otros tipos" + (" " + cola if cola else "")
    else:
        hoja = _minuscula_inicial(hoja)
    return f"{contexto}: {hoja}"


# --- Emoji -------------------------------------------------------------------

def _sin_tildes(texto: str) -> str:
    plano = unicodedata.normalize("NFD", texto)
    return "".join(c for c in plano if unicodedata.category(c) != "Mn").lower()


ALIM = {f"{n:02d}" for n in range(3, 20)}  # sectores de alimentación, bebidas y tabaco

# (patrón sobre la denominación sin tildes, emoji, sectores donde vale o None = todos).
# Gana la primera regla que encaje: las específicas van antes que las genéricas.
# El patrón se ancla al inicio de palabra, así que "ques" o "cervez" sirven de raíz.
REGLAS_EMOJI: list[tuple[str, str, set[str] | None]] = [
    # --- carne, pescado ---
    (r"jamon|paleta", "🍖", ALIM), (r"embutid|salchich|chorizo", "🌭", ALIM),
    (r"tocino|bacon|panceta", "🥓", ALIM), (r"poll|volateria|pavo|pato|aves\b", "🍗", {"03"}),
    (r"porcino|cerdo", "🐖", {"03"}), (r"bovino|vacuno|ternera", "🐄", {"03"}),
    (r"ovino|caprino|cordero", "🐑", {"03"}), (r"equino|caball", "🐎", {"03"}),
    (r"conejo|liebre", "🐇", {"03"}), (r"insecto", "🦗", ALIM),
    (r"crustaceo|gamba|langost|camaron", "🦐", {"04"}), (r"pulpo|calamar|sepia|cefalopodo", "🐙", {"04"}),
    (r"molusco|mejillon|almeja|ostra", "🦪", {"04"}),
    # --- frutas y hortalizas ---
    (r"patata", "🥔", ALIM), (r"tomate|ketchup", "🍅", ALIM), (r"aceituna", "🫒", ALIM),
    (r"zumo|jugo|nectar", "🧃", ALIM), (r"mermelada|confitura|jalea|compota", "🍓", ALIM),
    (r"frutos? secos?|cacahuete|almendra|nuez|nueces|avellana", "🥜", {"05", "11", "12"}),
    (r"seta|hongo|champinon", "🍄", ALIM), (r"maiz", "🌽", ALIM),
    (r"guisante|judia|legumbre", "🫘", {"05"}), (r"fruta", "🍑", {"05"}),
    # --- aceites, lácteos ---
    (r"oliva", "🫒", {"06"}), (r"girasol", "🌻", {"06"}), (r"margarina|mantequilla", "🧈", ALIM),
    (r"ques|requeson", "🧀", {"07"}), (r"yogur", "🥣", ALIM), (r"helado|sorbete", "🍦", ALIM),
    (r"leche|nata\b|lactosuero|caseina", "🥛", {"07"}),
    # --- molinería, pan, dulces ---
    (r"arroz", "🍚", ALIM), (r"harina|semola", "🌾", {"08"}),
    (r"pastas? alimenticias?|macarron|fideo|espagueti|cuscus", "🍝", ALIM),
    (r"galleta|barquillo|oblea", "🍪", ALIM), (r"pan fresco|pan rallado|pan tostado|colines", "🥖", ALIM),
    (r"bolleria|pastel|tarta", "🥐", ALIM), (r"pizza|empanada", "🍕", ALIM),
    (r"chicle|goma de mascar", "🫧", ALIM), (r"caramelo|confiteria sin cacao|regaliz|turron", "🍬", ALIM),
    (r"chocolate|cacao", "🍫", ALIM), (r"azucar|melaza|jarabe", "🍚", {"10"}),
    # --- otros alimentos, piensos ---
    (r"cafe", "☕", ALIM), (r"te\b|infusion", "🍵", {"12"}), (r"sal\b", "🧂", {"12"}),
    (r"vinagre", "🍶", {"12"}), (r"salsa|mayonesa|mostaza|condimento|especia", "🌶️", {"12"}),
    (r"sopa|caldo", "🍜", ALIM), (r"huevo", "🥚", ALIM), (r"levadura", "🍞", ALIM),
    (r"infantil|bebes|lactantes", "🍼", ALIM), (r"platos? preparad|comidas? preparad", "🍱", ALIM),
    (r"perros o gatos|animales domesticos|animales de compania", "🐶", {"13"}),
    (r"para porcino", "🐖", {"13"}), (r"para aves", "🐔", {"13"}), (r"para vacuno", "🐄", {"13"}),
    (r"para peces", "🐟", {"13"}),
    # --- bebidas, tabaco ---
    (r"whisky|ron\b|ginebra|vodka|brandy|aguardiente|licor", "🥃", {"14"}),
    (r"cava|espumoso|champan", "🍾", {"15"}), (r"vermu", "🍸", {"15"}), (r"vino|mosto", "🍷", {"15"}),
    (r"sidra", "🍏", ALIM), (r"cerveza", "🍺", ALIM), (r"malta", "🌾", {"17"}),
    (r"agua mineral|aguas sin edulcorar|hielo", "💧", {"18"}),
    # --- textil, ropa, cuero, calzado ---
    (r"mascarilla", "😷", None), (r"alfombra|moqueta", "🧶", {"22", "23"}),
    (r"cuerda|cordel|cordaje|redes?\b", "🪢", {"22", "23"}), (r"toalla|ropa de tocador", "🛁", {"22"}),
    (r"ropa de cama|sabana|manta|edredon|almohada", "🛏️", {"22"}), (r"cortina|visillo", "🪟", {"22"}),
    (r"tienda|toldo|vela", "⛺", {"22"}), (r"calcet|medias|pantis?", "🧦", {"24", "25"}),
    (r"sueter|jersey", "🧥", {"24", "25"}), (r"abrigo|chaqueton|anorak|impermeable", "🧥", {"25"}),
    (r"vestido|falda", "👗", {"25"}), (r"pantalon|vaquero", "👖", {"25"}),
    (r"camisa|blusa", "👔", {"25"}), (r"camiseta", "👕", {"24", "25"}), (r"traje", "🤵", {"25"}),
    (r"sosten|sujetador|faja|corse|braga|calzoncillo|ropa interior|lenceria", "🩲", {"24", "25"}),
    (r"banador|bano", "🩱", {"25"}), (r"guante", "🧤", {"25", "77"}), (r"sombrero|gorra|tocado", "🧢", {"25"}),
    (r"corbata|panuelo|bufanda|chal", "🧣", {"25"}), (r"bebes", "👶", {"25"}),
    (r"peleteria", "🦊", {"25", "26"}), (r"maleta|baul|bolso", "🧳", {"27"}),
    (r"sandalia", "🩴", {"28"}), (r"bota", "🥾", {"28"}), (r"deport", "👟", {"28"}),
    (r"mujer|senora", "👠", {"28"}),
    # --- madera, papel, impresión ---
    (r"corcho|tapon", "🍾", {"30"}), (r"parque|parquet|tablero", "🪵", {"29", "30"}),
    (r"puerta|ventana", "🚪", {"30", "45", "54"}), (r"palet|caja|envase|embalaje", "📦", {"30", "32"}),
    (r"ataud", "⚰️", None), (r"higienico|panal|compresa|panuelo|servilleta", "🧻", {"31", "32"}),
    (r"cuaderno|libros? de registro|sobre|carpeta|papeleria", "📒", {"32"}), (r"etiqueta", "🏷️", {"32"}),
    (r"papel pintado", "🖼️", {"32"}), (r"diario|periodic|revista", "📰", {"33"}),
    (r"libro", "📚", {"33"}), (r"sello|billete", "💶", {"33"}),
    # --- química, farmacia, plástico ---
    (r"hidrogeno|oxigeno|nitrogeno|argon|dioxido de carbono|gases raros", "🫧", {"34"}),
    (r"uranio|plutonio|radiactiv|isotopo", "☢️", None), (r"acido", "⚗️", {"34", "36"}),
    (r"insecticida|herbicida|fungicida|raticida|plaguicida|desinfectante", "🐛", {"37"}),
    (r"abono|fertilizante|nitrato|urea|amoniaco", "🌱", {"37"}),
    (r"tinta", "🖋️", {"39"}), (r"pintura|barniz|esmalte", "🖌️", {"39"}),
    (r"perfume|agua de tocador", "🌸", {"40"}), (r"maquillaje|labio|ojos|manicura|belleza", "💄", {"40"}),
    (r"champu|laca|capilar|cabello", "🧴", {"40"}), (r"dentifric|dental|bucal", "🪥", {"40"}),
    (r"afeitar|desodorante", "🪒", {"40"}), (r"jabon", "🧼", {"40"}),
    (r"detergente|lavar|limpieza|tensioactiv", "🧽", {"40"}), (r"vela|bujia", "🕯️", {"40", "41"}),
    (r"explosivo|polvora|detonador|pirotecni|fuegos artificiales", "🧨", None),
    (r"cola|adhesivo|pegamento", "🧷", {"41"}), (r"aceites esenciales", "🌿", {"41"}),
    (r"fotograf", "📷", {"41", "60"}), (r"biodiesel|biocombustible|bioetanol", "🌿", None),
    (r"vacuna|suero", "💉", {"43"}), (r"contienen (?:penicilin|otros antibiotic|antibiotic)|penicilina", "🦠", {"43"}),
    (r"contienen hormonas|insulina", "🧬", {"43"}), (r"provitaminas|vitaminas y", "🍊", {"43"}),
    (r"aposito|vendaje|venda|esparadrapo|gasas?\b", "🩹", {"43"}),
    (r"neumatico|cubierta", "🛞", {"44"}),
    (r"bolsa|saco", "🛍️", {"45"}), (r"botella|bombona|frasco", "🧴", {"45"}),
    (r"tubo|tuberia", "🚰", {"45"}), (r"banera|ducha|lavabo|sanitari", "🛁", {"45", "47"}),
    # --- vidrio, cerámica, construcción ---
    (r"botella|tarro|frasco|envase", "🍾", {"46"}), (r"vaso|copa|cristaleria|vajilla", "🥂", {"46"}),
    (r"espejo", "🪞", {"46"}), (r"vajilla|mesa o cocina|porcelana", "🍽️", {"47"}),
    (r"fregadero|inodoro", "🚽", {"47"}), (r"aislador|aislante", "🔌", {"47"}),
    (r"teja", "🏠", {"48"}), (r"ladrillo", "🧱", {"48"}), (r"baldosa|azulejo", "🔲", {"48"}),
    (r"yeso|escayola", "🧱", {"49"}), (r"marmol|granito|pizarra", "🪨", {"50"}),
    (r"asfalt|betun|bitum", "🛣️", {"50"}),
    # --- metales y productos metálicos ---
    (r"oro\b", "🥇", {"52", "73"}), (r"plata\b", "🥈", {"52", "73"}), (r"platino", "💎", {"52"}),
    (r"cobre|laton", "🟠", {"52", "53"}), (r"aluminio", "🥫", {"52"}),
    (r"plomo|cinc|zinc|estano|niquel", "🔘", {"52"}),
    (r"alambre|cable", "➰", {"51", "52", "57"}), (r"carril|rail", "🛤️", {"51"}),
    (r"radiador|caldera", "♨️", {"54"}), (r"deposito|cisterna|cuba|tanque", "🛢️", {"54"}),
    (r"torre|castillete|puente", "🌉", {"54"}),
    (r"cuchill|cuchar|tenedor|cubert", "🍴", {"56"}), (r"tijera", "✂️", {"56"}),
    (r"maquinilla|hojas? de afeitar|navaja", "🪒", {"56"}), (r"cerradura|candado", "🔐", {"56"}),
    (r"sierra", "🪚", {"56", "64"}), (r"martillo|mazo", "🔨", {"56"}),
    (r"llave|alicate|destornillador", "🔧", {"56"}), (r"bisagra|herraje", "🚪", {"56"}),
    (r"pistola|revolver|fusil|escopeta|carabina|armas?\b", "🔫", {"57"}),
    (r"municion|cartucho|bomba|granada|misil|torpedo", "💣", {"57"}),
    (r"carros? de combate|blindado", "🪖", None), (r"tornill|perno|tuerca|remache", "🔩", {"57"}),
    (r"muelle|resorte", "➰", {"57"}), (r"cadena", "⛓️", {"57"}), (r"aguja|alfiler", "🪡", {"57"}),
    (r"lata|bidon|barril|envase", "🥫", {"57"}), (r"caja fuerte|cajas? de caudales", "🔐", {"57"}),
    (r"cacerola|sarten|cocina|domestic", "🍳", {"57"}),
    # --- electrónica, instrumentos, eléctrico ---
    (r"semiconductor|circuitos? integrad|diodo|transistor|microprocesador", "🔲", {"58"}),
    (r"portatil", "💻", {"58"}), (r"ordenador|procesamiento de datos", "🖥️", {"58"}),
    (r"impresora", "🖨️", {"58"}), (r"teclado", "⌨️", {"58"}), (r"monitor|pantalla", "🖥️", {"58"}),
    (r"telefon", "📱", {"58"}), (r"television|televisor", "📺", {"58"}), (r"camara", "📹", {"58", "60"}),
    (r"radio", "📻", {"58"}), (r"altavoz|auricular|microfono|sonido", "🔊", {"58"}),
    (r"antena|radar|radionavegacion", "📡", {"58", "59"}),
    (r"reloj", "⌚", {"59"}), (r"termometro|termostato", "🌡️", {"59"}),
    (r"brujula|navegacion", "🧭", {"59"}), (r"balanza|bascula", "⚖️", {"59", "63"}),
    (r"rayos x|radiologi|tomograf", "🩻", {"60"}), (r"marcapasos|audifono", "🫀", {"60"}),
    (r"microscopio", "🔬", {"60"}), (r"telescopio|prismatico|binocular", "🔭", {"60"}),
    (r"lente|gafas", "👓", {"60", "76"}), (r"laser", "🔦", {"60"}),
    (r"pilas?\b|bateria|acumulador", "🔋", {"61"}),
    (r"lampara|luminaria|alumbrado|bombilla|iluminacion", "💡", {"61"}),
    (r"fibras? optica", "🌐", {"61"}), (r"cable|hilo|conductor", "🔌", {"61"}),
    (r"transformador", "🔌", {"61"}), (r"motor|generador|alternador", "⚡", {"61"}),
    (r"interruptor|enchufe|fusible|rele|cuadro", "🎛️", {"61"}), (r"alarma|sirena|senalizacion", "🚨", {"61"}),
    (r"frigorifico|congelador|refrigerador", "🧊", {"62"}), (r"lavavajillas", "🍽️", {"62"}),
    (r"lavadora|secadora", "🧺", {"62"}), (r"aspirador", "🧹", {"62"}), (r"plancha", "👔", {"62"}),
    (r"cafetera", "☕", {"62"}), (r"tostador", "🍞", {"62"}),
    (r"horno|microondas|cocina|hornillo", "🍳", {"62"}),
    (r"afeitar|depilar|secador|cabello", "💇", {"62"}), (r"ventilador|campana", "🌬️", {"62"}),
    (r"calentador|calefaccion|radiador|estufa", "♨️", {"62"}),
    # --- maquinaria ---
    (r"turbina", "🌀", {"63"}), (r"bomba", "⛽", {"63"}), (r"compresor", "🌬️", {"63"}),
    (r"grifo|valvula", "🚰", {"63"}), (r"rodamiento|engranaje", "⚙️", {"63"}),
    (r"ascensor|escaleras? mecanica|montacargas", "🛗", {"63"}),
    (r"grua|carretilla|elevador|polipasto", "🏗️", {"63", "66"}),
    (r"aire acondicionado|acondicionador|climatizacion", "❄️", {"63"}),
    (r"frigorific|refrigeracion|congela", "🧊", {"63"}), (r"extintor", "🧯", {"63"}),
    (r"horno|quemador", "🔥", {"63"}), (r"soldar|soldadura", "👨‍🏭", {"63", "64"}),
    (r"taladr|perfora", "🪛", {"64", "66"}), (r"tractor", "🚜", {"65"}),
    (r"cosechadora|segadora|cortacesped", "🌾", {"65"}), (r"arado|sembradora|abonadora", "🌱", {"65"}),
    (r"excavadora|bulldozer|niveladora|pala", "🚧", {"66"}),
    (r"coser|textil|tejer|hilar", "🧵", {"66"}), (r"imprimir|imprenta", "🖨️", {"66"}),
    (r"robot", "🤖", None),
    # --- transporte ---
    (r"autobus|autocar|transporte de (?:>|≥) ?=? ?10", "🚌", {"67"}),
    (r"partes y accesorios", "🔩", {"67"}), (r"camion|mercancias", "🚚", {"67"}), (r"autocaravana|caravana", "🚐", {"67"}),
    (r"remolque|semirremolque", "🚛", {"67"}), (r"ambulancia", "🚑", {"67"}),
    (r"bomberos|incendios", "🚒", {"67"}), (r"asiento", "💺", {"67"}),
    (r"motor electrico|(?<!no )electricos?\b|hibrid", "🔋", {"67"}),
    (r"motores?\b", "⚙️", {"67"}), (r"freno", "🛑", {"67"}), (r"cinturon|airbag", "🦺", {"67"}),
    (r"velero|vela", "⛵", {"68"}), (r"recreo|deport|yate", "🛥️", {"68"}),
    (r"pesquero|pesca", "🎣", {"68"}), (r"guerra|militar", "⚓", {"68"}),
    (r"locomotora", "🚂", {"69"}), (r"tranvia|metro\b", "🚊", {"69"}),
    (r"avion", "✈️", {"70"}), (r"helicoptero", "🚁", {"70"}), (r"satelite|espacial|lanzamiento", "🛰️", {"70"}),
    (r"bicicleta|ciclos?\b", "🚲", {"71"}), (r"sillas? de ruedas|invalido|discapacit", "🦽", {"71"}),
    (r"cochecito|coches? para ninos", "👶", {"71"}), (r"scooter|ciclomotor", "🛵", {"71"}),
    # --- muebles, joyería, ocio, médico, otros ---
    (r"colchon|somier", "🛏️", {"72"}), (r"cocina", "🍳", {"72"}), (r"dormitorio|cama", "🛏️", {"72"}),
    (r"oficina", "🗄️", {"72"}), (r"sofa|tapizad", "🛋️", {"72"}),
    (r"moneda|medalla", "🪙", {"73"}), (r"perla|diamante|piedras preciosas", "💎", {"73"}),
    (r"piano|organo|teclado", "🎹", {"74"}), (r"guitarra|cuerda", "🎸", {"74"}),
    (r"viento|trompeta|flauta", "🎺", {"74"}), (r"percusion|tambor|bateria", "🥁", {"74"}),
    (r"esqui|nieve|patin", "⛷️", {"75"}), (r"pesca|cana", "🎣", {"75"}),
    (r"balon|pelota", "⚽", {"75"}), (r"raqueta|tenis", "🎾", {"75"}), (r"golf", "⛳", {"75"}),
    (r"gimnasi|atletismo|cultura fisica", "🏋️", {"75"}), (r"piscina|acuatic|vela|tabla", "🏄", {"75"}),
    (r"muneca|muneco", "🪆", {"75"}), (r"puzzle|rompecabezas", "🧩", {"75"}),
    (r"naipe|cartas", "🃏", {"75"}), (r"videojuego|videoconsola|consola", "🎮", {"75"}),
    (r"billar|casino|bolos|recreativ", "🎱", {"75"}), (r"navidad|feria|carnaval|fiesta", "🎄", {"75", "77"}),
    (r"jeringa|aguja|cateter|canula", "💉", {"76"}), (r"dental|dentist|dentadura|diente", "🦷", {"76"}),
    (r"protesis|ortoped|articulacion", "🦿", {"76"}),
    (r"cepillos? de dientes", "🪥", {"77"}), (r"escoba|cepillo|brocha|pincel", "🧹", {"77"}),
    (r"boligrafo|pluma|lapiz|lapices|rotulador", "🖊️", {"77"}), (r"paraguas|sombrilla", "☂️", {"77"}),
    (r"casco", "⛑️", {"77"}), (r"encendedor|mechero|cerilla|fosforo", "🔥", {"77"}),
    (r"boton|cremallera", "🧷", {"77"}), (r"peine|peluca", "💇", {"77"}),
    (r"aeronave|avion", "✈️", {"78"}), (r"buque|barco|embarcacion|naval", "🚢", {"78"}),
    (r"ferroviari", "🚆", {"78"}),
    # --- energía y petróleo ---
    (r"nuclear", "⚛️", {"79"}), (r"eolica", "🌬️", {"79"}), (r"solar|fotovoltaic", "☀️", {"79"}),
    (r"hidroelectric|hidraulica", "💧", {"79"}), (r"vapor|agua caliente", "♨️", {"79"}),
    (r"gas\b", "🔥", {"79"}), (r"queroseno", "✈️", {"81"}), (r"gasolina|diesel|gasoleo", "⛽", {"81"}),
    (r"butano|propano|glp|gases de petroleo", "🔥", {"81"}),
]
_COMPILADAS: list[tuple[re.Pattern, str, set[str] | None]] = []
_EXCEPCIONES = re.compile(r"\((?:excep|exclui|no inclu|sin incluir)[^)]*\)?")


def emoji_de(ruta: list[str], sector: str) -> str:
    if not _COMPILADAS:
        _COMPILADAS.extend(
            (re.compile(r"\b(?:" + p + r")", re.I), e, s) for p, e, s in REGLAS_EMOJI
        )
    # "(excepto cerveza)" no debe hacer que el producto parezca cerveza
    # Primero se mira solo la hoja (lo que el producto es) y después toda la jerarquía.
    for trozo in (ruta[-1:], ruta):
        texto = _EXCEPCIONES.sub(" ", _sin_tildes(" ".join(trozo)))
        for patron, emoji, sectores in _COMPILADAS:
            if (sectores is None or sector in sectores) and patron.search(texto):
                return emoji
    return SECTORES.get(sector, ("🏭", ""))[0]


# --- Nombres puestos a mano ----------------------------------------------------
# Código PRODCOM -> nombre corto. Tienen prioridad sobre el nombre automático.
# Están los productos de más valor; añade aquí los que quieras renombrar.
RENOMBRES: dict[str, str] = {
    "1920265096": "Gasóleo de automoción (diésel)",
    "1920267092": "Gasóleo de calefacción",
    "1920215091": "Gasolina sin plomo",
    "1920240099": "Queroseno (combustible de aviación)",
    "1920235099": "Nafta ligera para la industria petroquímica",
    "2910210000": "Coches de gasolina de hasta 1.500 cm³",
    "2910223003": "Coches de gasolina de más de 1.500 cm³",
    "2910231006": "Coches diésel de hasta 1.500 cm³",
    "2910233002": "Coches diésel de 1.500 a 2.500 cm³",
    "2910249008": "Otros coches (híbridos, eléctricos y demás)",
    "2910421306": "Camiones y furgonetas eléctricos",
    "2910120004": "Motores de gasolina para vehículos, de más de 1.000 cm³",
    "2932209006": "Piezas y accesorios de carrocería para vehículos",
    "2932309002": "Otras piezas y accesorios no eléctricos para vehículos",
    "2932100000": "Asientos para automóviles",
    "2229916007": "Piezas de plástico para vehículos (fabricación por encargo)",
    "2550121000": "Piezas de acero estampadas para vehículos",
    "2211110001": "Neumáticos nuevos para turismos",
    "3511102091": "Electricidad térmica de cogeneración (calor y electricidad)",
    "3511103099": "Electricidad térmica convencional (sin cogeneración)",
    "3511105094": "Electricidad nuclear",
    "3511107398": "Electricidad eólica",
    "3511107596": "Electricidad solar fotovoltaica",
    "3511107292": "Electricidad hidroeléctrica",
    "1011129001": "Carne de cerdo fresca: otras piezas",
    "1011125009": "Jamones y paletas de cerdo frescos, con hueso",
    "1011329002": "Carne de cerdo congelada: otras piezas",
    "1011119002": "Carne de vacuno fresca, despiezada",
    "1011114003": "Carne de vacuno fresca, en canales y cuartos",
    "1012105009": "Pollo fresco en piezas",
    "1012101008": "Pollos enteros frescos",
    "1013112003": "Jamones y paletas curados, con hueso",
    "1013154501": "Jamón cocido y jamón curado deshuesado",
    "1013146108": "Embutidos: chorizo, salchichón, salchichas, mortadela, patés…",
    "1020254023": "Conservas de atún y bonito",
    "1039177001": "Aceitunas de mesa",
    "1041221019": "Aceite de oliva virgen extra",
    "1051405003": "Quesos curados, semicurados, azules y rallados",
    "1051114201": "Leche y nata líquidas en envases de hasta 2 litros",
    "1071110014": "Pan fresco (barras, hogazas; no de molde)",
    "1071120004": "Bollería y pastelería fresca",
    "1072199006": "Pizzas, empanadas, churros y masas",
    "1083115009": "Café tostado sin descafeinar",
    "1091103306": "Pienso para cerdos",
    "1091103504": "Pienso para vacas, ovejas, cabras, caballos y conejos",
    "1091103703": "Pienso para aves",
    "1092103006": "Comida para perros y gatos",
    "1105100001": "Cerveza con alcohol",
    "1107195034": "Refrescos (colas, limonadas, etc.)",
    "1107113000": "Agua mineral y agua con gas",
    "1102121718": "Vino tinto con denominación de origen",
    "1721130003": "Cajas de cartón ondulado",
    "2120138105": "Medicamentos sin hormonas ni antibióticos (los demás)",
    "2331100006": "Azulejos y baldosas de cerámica",
    "2351121028": "Cemento portland (otros tipos)",
    "2363100009": "Hormigón fresco (preparado)",
    "2361120001": "Prefabricados de hormigón: vigas, bovedillas, traviesas, placas…",
    "2444133005": "Cobre refinado en bruto, sin alear",
    "2442225000": "Barras y perfiles de aleación de aluminio",
    "2732138001": "Cables eléctricos de baja tensión (hasta 1.000 V)",
    "2512105003": "Puertas y ventanas de aluminio",
    "2511103000": "Construcciones prefabricadas de hierro y acero",
    "2511235503": "Grandes estructuras de acero: compuertas, muelles, esclusas…",
    "2511000994": "Montaje en obra de estructuras metálicas propias",
    "2550000992": "Servicio de corte de metales",
    "3030509105": "Piezas de aviones, helicópteros y naves espaciales (uso civil)",
    "3020320008": "Vagones de pasajeros para ferrocarril",
    "3316100005": "Reparación y mantenimiento de aviones civiles",
    "3317110002": "Reparación y mantenimiento de trenes",
}


def nombre_de(prodcom: str, ruta: list[str]) -> str:
    """Nombre a mostrar: el puesto a mano si existe; si no, el automático."""
    return RENOMBRES.get(prodcom) or nombre_claro(ruta)
