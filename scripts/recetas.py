#!/usr/bin/env python3
"""Recetas: qué lleva cada producto final tal como se vende. **Edítalo para afinar.**

Uso:
    python scripts/recetas.py        # comprueba las recetas y escribe data/recetas.json

Una pechuga de pollo no se vende sola: va en una bandeja de plástico, con film,
etiqueta, dentro de una caja de cartón y sobre un palé. La página «Producción
final» (final.html) suma todo eso: unidades, valor y horas de trabajo del
producto y de cada envase o ingrediente que la encuesta del INE también mide.

Cada receta da, por kilo (o por litro) de producto, cuánto lleva de cada
componente. La página multiplica por la producción del año y valora cada
componente al precio medio que da la misma encuesta (valor / cantidad).

LAS CANTIDADES POR UNIDAD NO SON DATOS DEL INE: son estimaciones del formato de
venta típico (peso de una bandeja, de una botella, de un brik…), explicadas en la
nota de cada componente. Cámbialas aquí si tienes un dato mejor.

Componente: (alias de COMPONENTES, cantidad por kg o litro de producto, nota).
La cantidad va en la unidad de la tercera columna de COMPONENTES.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PRODUCCION = RAIZ / "data" / "produccion.json"
SALIDA = RAIZ / "data" / "recetas.json"

# --- Componentes: productos de la encuesta que van dentro de otros -----------------
# alias: (código PRODCOM, nombre corto, unidad de la receta, unidades de la receta por
#         unidad de la encuesta)
COMPONENTES: dict[str, tuple[str, str, str, float]] = {
    # Plástico
    "BANDEJA": ("2222130006", "Bandejas y cajas de plástico", "kg", 1000),
    "FILM": ("2221301000", "Film de polietileno (≤ 0,125 mm)", "kg", 1000),
    "FILM_BOPP": ("2221302105", "Film de polipropileno biorientado", "kg", 1000),
    "BOLSA": ("2222110008", "Bolsas de polietileno", "kg", 1000),
    "BOLSA_MULTICAPA": ("2222120007", "Bolsas y láminas de otros plásticos (vacío, multicapa)", "kg", 1000),
    "PET": ("2222145004", "Botellas de plástico hasta 2 l", "uds", 1000),
    "GARRAFA": ("2222147000", "Botellas y garrafas de plástico de más de 2 l", "uds", 1000),
    "TAPON": ("2222192502", "Tapones y tapas de plástico", "kg", 1000),
    "TRIPA": ("2221213009", "Tripas artificiales", "kg", 1000),
    # Vidrio
    "BOTELLA_COLOR": ("2313115002", "Botellas de vidrio de color", "uds", 1000),
    "BOTELLA_BLANCA": ("2313114005", "Botellas de vidrio incoloro", "uds", 1000),
    "TARRO": ("2313116000", "Tarros de vidrio para alimentos", "uds", 1000),
    "FRASCO": ("2313118006", "Frascos de vidrio (perfumería y otros)", "uds", 1000),
    # Metal
    "LATA": ("2592113307", "Latas de conserva para alimentos", "uds", 1),
    # El INE publica esta línea en «kilogramos», pero a 0,05 € el «kilo» solo cuadra
    # si son latas: se toma cada «kilogramo» como una lata.
    "LATA_BEBIDA": ("2592124006", "Latas de aluminio para bebidas", "uds", 1),
    "CORONA": ("2592133007", "Tapones corona", "uds", 1),
    "TAPA_METAL": ("2592137008", "Tapas y cápsulas metálicas (twist-off, bozales…)", "kg", 1000),
    "CAPSULA": ("2592135002", "Cápsulas de aluminio (capuchones, roscas de vino)", "kg", 1000),
    # Corcho
    "CORCHO": ("1629225005", "Tapones de corcho natural", "kg", 1),
    "CORCHO_AGLOMERADO": ("1629232001", "Corcho aglomerado (tapones de cava)", "kg", 1),
    # Papel y cartón
    "CAJA": ("1721130003", "Cajas de cartón ondulado", "kg", 1000),
    # El brik (cartón para líquidos) va en esta partida (SA 4819.20).
    "ESTUCHE": ("1721140002", "Estuches, briks y cartonajes plegables", "kg", 1000),
    "ENVASE_HELADO": ("1721153005", "Otros envases de cartón (helados…)", "kg", 1000),
    "BOLSA_PAPEL": ("1721125003", "Bolsas y sacos de papel", "kg", 1000),
    "TUBO_CARTON": ("1729193004", "Tubos y otros artículos de cartón", "kg", 1000),
    "ETIQUETA": ("1729112004", "Etiquetas autoadhesivas", "kg", 1000),
    # Madera
    "PALE": ("1624113305", "Palés de madera", "uds", 1),
    # Ingredientes que la encuesta también mide
    "HARINA": ("1061210001", "Harina de trigo", "kg", 1000),
    "MALTA": ("1106103003", "Malta", "kg", 1000),
    "ACEITE": ("1041540004", "Aceite de girasol refinado", "kg", 1000),
}

# Un palé nuevo cada ~5 t de mercancía (los palés se reutilizan varias veces).
PALE = ("PALE", 0.0002, "Un palé nuevo por cada ~5 t: los palés se reutilizan")

# --- Recetas ----------------------------------------------------------------------
# (id, emoji, nombre, familia, códigos PRODCOM del producto, formato de venta, componentes)
RECETAS: list[tuple[str, str, str, str, list[str], str, list[tuple[str, float, str]]]] = [
    ("POLLO_PIEZAS", "🍗", "Pollo en piezas (pechugas, muslos…)", "Carne y embutidos", ["1012105009"],
     "80 % en bandeja de ~500 g con film y etiqueta; el resto a granel en caja (hostelería e industria)",
     [("BANDEJA", 0.026, "Bandeja de ~16 g por 500 g, en el 80 %"),
      ("FILM", 0.0064, "Film de cierre de ~4 g por bandeja"),
      ("ETIQUETA", 0.0016, "Etiqueta de ~1 g por bandeja"),
      ("CAJA", 0.04, "Caja de cartón de ~450 g por cada 10-12 kg"), PALE]),
    ("POLLO_ENTERO", "🐔", "Pollo entero", "Carne y embutidos", ["1012101008"],
     "70 % en bolsa individual (~1,8 kg); todo en caja de cartón",
     [("BOLSA", 0.003, "Bolsa de ~8 g por pollo, en el 70 %"),
      ("ETIQUETA", 0.0005, "Etiqueta de ~1 g por pollo"),
      ("CAJA", 0.04, "Caja de cartón de ~450 g por cada 10-12 kg"), PALE]),
    ("CERDO", "🥩", "Carne de cerdo fresca en piezas", "Carne y embutidos", ["1011129001"],
     "La mitad en bandeja de ~600 g; la otra mitad en caja con bolsa interior (exportación e industria)",
     [("BANDEJA", 0.0133, "Bandeja de ~16 g por 600 g, en la mitad"),
      ("FILM", 0.0033, "Film de ~4 g por bandeja"),
      ("BOLSA", 0.0015, "Bolsa interior de ~60 g por caja de 20 kg, en la otra mitad"),
      ("ETIQUETA", 0.0008, "Etiqueta de ~1 g por bandeja"),
      ("CAJA", 0.035, "Caja de cartón de ~700 g por 20 kg"), PALE]),
    ("VACUNO", "🐄", "Carne de vacuno despiezada", "Carne y embutidos", ["1011119002"],
     "60 % en piezas envasadas al vacío; 40 % en bandeja de ~500 g",
     [("BOLSA_MULTICAPA", 0.009, "Bolsa de vacío de ~15 g por kg, en el 60 %"),
      ("BANDEJA", 0.0128, "Bandeja de ~16 g por 500 g, en el 40 %"),
      ("FILM", 0.0032, "Film de ~4 g por bandeja"),
      ("ETIQUETA", 0.002, "Etiqueta por pieza o bandeja"),
      ("CAJA", 0.035, "Caja de cartón de ~700 g por 20 kg"), PALE]),
    ("EMBUTIDOS", "🌭", "Chorizo, salchichón, salchichas y mortadela", "Carne y embutidos", ["1013146108"],
     "Embutido en tripa artificial; envasado al vacío o en atmósfera protectora",
     [("TRIPA", 0.006, "~6 g de tripa artificial por kg (parte va en tripa natural)"),
      ("BOLSA_MULTICAPA", 0.02, "Envase de vacío o atmósfera protectora, ~20 g por kg"),
      ("ETIQUETA", 0.002, "Etiqueta por envase"),
      ("CAJA", 0.035, "Caja de cartón"), PALE]),
    ("JAMON_COCIDO", "🥪", "Jamón cocido y jamón curado deshuesado", "Carne y embutidos", ["1013154501"],
     "La mitad loncheado en barqueta de ~150 g; la otra mitad en pieza al vacío",
     [("BANDEJA", 0.033, "Barqueta de ~10 g por 150 g, en la mitad"),
      ("FILM", 0.01, "Film de cierre de ~3 g por barqueta"),
      ("BOLSA_MULTICAPA", 0.0075, "Bolsa de vacío de ~15 g por kg, en la otra mitad"),
      ("ETIQUETA", 0.004, "Etiqueta por envase"),
      ("CAJA", 0.03, "Caja de cartón"), PALE]),
    ("JAMON_CURADO", "🍖", "Jamones y paletas curados con hueso", "Carne y embutidos", ["1013112003"],
     "Pieza entera de ~8 kg con funda, etiqueta y caja individual",
     [("BOLSA", 0.004, "Funda o malla de ~30 g por pieza"),
      ("ETIQUETA", 0.0005, "Etiqueta por pieza"),
      ("CAJA", 0.06, "Caja de ~500 g por pieza de 8 kg"), PALE]),
    ("QUESO", "🧀", "Quesos curados y semicurados", "Lácteos", ["1051405003"],
     "Pieza de ~3 kg con lámina plástica, o cuñas al vacío; en caja de cartón",
     [("BOLSA_MULTICAPA", 0.008, "Lámina o bolsa de vacío, ~8 g por kg"),
      ("ETIQUETA", 0.001, "Etiqueta por pieza"),
      ("CAJA", 0.05, "Caja de cartón por cada 2-4 piezas"), PALE]),
    ("LECHE", "🥛", "Leche en envases de hasta 2 litros", "Lácteos", ["1051114201"],
     "Brik de 1 l (~28 g: cartón, polietileno y aluminio) con tapón, en bandeja de 6 con film",
     [("ESTUCHE", 0.027, "Brik de ~28 g por litro"),
      ("TAPON", 0.0024, "Tapón de ~2,5 g por brik"),
      ("CAJA", 0.012, "Bandeja de cartón de ~70 g por 6 briks"),
      ("FILM", 0.004, "Film retráctil de ~25 g por 6 briks"), PALE]),
    ("YOGUR", "🍶", "Yogures y leches fermentadas", "Lácteos", ["1051524400"],
     "Vaso de plástico de 125 g en pack de 4 con faja de cartón (la tapa no se cuenta)",
     [("BANDEJA", 0.032, "Vaso de ~4 g por 125 g (plástico termoformado)"),
      ("ESTUCHE", 0.02, "Faja de cartón de ~10 g por pack de 4"),
      ("CAJA", 0.02, "Caja de cartón"), PALE]),
    ("HELADOS", "🍦", "Helados", "Lácteos", ["1052100006"],
     "Tarrinas y envases de cartón, polos y conos con envoltorio",
     [("ENVASE_HELADO", 0.03, "Envase de cartón, ~30 g por litro"),
      ("BANDEJA", 0.01, "Tarrinas de plástico, ~10 g por litro"),
      ("FILM", 0.004, "Envoltorios"),
      ("CAJA", 0.02, "Caja de cartón"), PALE]),
    ("AOVE", "🫒", "Aceite de oliva virgen extra", "Aceites", ["1041221019"],
     "La mitad sale a granel (cisterna); la otra mitad en vidrio de 0,75 l (40 %) o PET de 1 l (60 %)",
     [("BOTELLA_BLANCA", 0.29, "0,55 l envasados por kg × 40 % ÷ 0,75 l"),
      ("PET", 0.33, "0,55 l envasados por kg × 60 % ÷ 1 l"),
      ("TAPON", 0.0016, "Tapón de ~2,5 g por botella"),
      ("ETIQUETA", 0.0006, "Etiqueta de ~1 g por botella"),
      ("CAJA", 0.018, "Caja de ~400 g por 12 l envasados"), PALE]),
    ("GIRASOL", "🌻", "Aceite de girasol refinado", "Aceites", ["1041540004"],
     "85 % en botella de PET de 1 l; el resto a granel para la industria",
     [("PET", 0.93, "1,09 l por kg × 85 %"),
      ("TAPON", 0.0023, "Tapón de ~2,5 g por botella"),
      ("ETIQUETA", 0.0009, "Etiqueta de ~1 g por botella"),
      ("CAJA", 0.03, "Caja de ~450 g por 15 botellas"),
      ("FILM", 0.003, "Film retráctil del palé"), PALE]),
    ("REFRESCOS", "🥤", "Refrescos (colas, limonadas…)", "Bebidas", ["1107195034"],
     "Por litro: 55 % en PET de 1,5 l, 30 % en lata de 33 cl, 5 % en vidrio de un solo uso de 25 cl; "
     "el resto en vidrio retornable y grifo",
     [("PET", 0.37, "0,55 l ÷ 1,5 l"),
      ("LATA_BEBIDA", 0.9, "0,30 l ÷ 0,33 l"),
      ("BOTELLA_BLANCA", 0.2, "0,05 l ÷ 0,25 l"),
      ("CORONA", 0.6, "Botellas de vidrio, también las retornables"),
      ("TAPON", 0.0009, "Tapón de ~2,5 g por botella de PET"),
      ("CAJA", 0.015, "Bandejas y cajas de cartón"),
      ("FILM", 0.006, "Film de los packs"), PALE]),
    ("AGUA", "💧", "Agua mineral y con gas", "Bebidas", ["1107113000"],
     "Por litro: 80 % en PET de 1,5 l, 15 % en garrafa de 5 l, 5 % en vidrio de 1 l",
     [("PET", 0.53, "0,80 l ÷ 1,5 l"),
      ("GARRAFA", 0.03, "0,15 l ÷ 5 l"),
      ("BOTELLA_BLANCA", 0.05, "0,05 l ÷ 1 l"),
      ("TAPON", 0.0015, "Tapón de ~2,5 g por botella"),
      ("FILM", 0.006, "Film de los packs de 6"), PALE]),
    ("CERVEZA", "🍺", "Cerveza", "Bebidas", ["1105100001"],
     "Por litro: 30 % en botella no retornable de 33 cl, 25 % en retornable de 20-25 cl, 25 % en lata de 33 cl, "
     "20 % en barril",
     [("MALTA", 0.15, "~150 g de malta por litro"),
      ("BOTELLA_COLOR", 0.9, "0,30 l ÷ 0,33 l (las retornables no se fabrican cada año)"),
      ("CORONA", 2.1, "Una chapa por botella, también las retornables"),
      ("LATA_BEBIDA", 0.76, "0,25 l ÷ 0,33 l"),
      ("ETIQUETA", 0.0012, "Etiquetas de las botellas"),
      ("CAJA", 0.02, "Cajas y bandejas de cartón"),
      ("FILM", 0.004, "Film de los packs"), PALE]),
    ("VINO_TINTO", "🍷", "Vino tinto con denominación de origen", "Bebidas", ["1102121718"],
     "80 % embotellado en 0,75 l, con corcho (60 %) o rosca, cápsula y etiqueta; en caja de 6",
     [("BOTELLA_COLOR", 1.07, "0,80 l ÷ 0,75 l"),
      ("CORCHO", 0.0026, "Tapón de ~4 g en el 60 % de las botellas"),
      ("CAPSULA", 0.0016, "Cápsula o rosca de ~1,5 g por botella"),
      ("ETIQUETA", 0.0021, "Etiqueta y contraetiqueta de ~2 g"),
      ("CAJA", 0.067, "Caja de ~300 g por 6 botellas"), PALE]),
    ("VINO_BLANCO", "🥂", "Vino blanco con denominación de origen", "Bebidas", ["1102121101"],
     "80 % embotellado en 0,75 l, con corcho (60 %) o rosca, cápsula y etiqueta; en caja de 6",
     [("BOTELLA_COLOR", 1.07, "0,80 l ÷ 0,75 l"),
      ("CORCHO", 0.0026, "Tapón de ~4 g en el 60 % de las botellas"),
      ("CAPSULA", 0.0016, "Cápsula o rosca de ~1,5 g por botella"),
      ("ETIQUETA", 0.0021, "Etiqueta y contraetiqueta de ~2 g"),
      ("CAJA", 0.067, "Caja de ~300 g por 6 botellas"), PALE]),
    ("CAVA", "🍾", "Cava y otros espumosos", "Bebidas", ["1102119017"],
     "Botella de 0,75 l con tapón de corcho aglomerado, bozal, capuchón y etiqueta; en caja de 6",
     [("BOTELLA_COLOR", 1.33, "1 l ÷ 0,75 l"),
      ("CORCHO_AGLOMERADO", 0.0133, "Tapón de ~10 g por botella"),
      ("TAPA_METAL", 0.004, "Bozal y chapa de ~3 g por botella"),
      ("CAPSULA", 0.0027, "Capuchón de ~2 g por botella"),
      ("ETIQUETA", 0.0027, "Etiquetas de ~2 g por botella"),
      ("CAJA", 0.067, "Caja de ~300 g por 6 botellas"), PALE]),
    ("ATUN", "🐟", "Conservas de atún y bonito", "Conservas", ["1020254023"],
     "Lata de ~125 g de media (de la RO-85 a la familiar) con aceite, en estuche de 3",
     [("LATA", 8, "1 kg ÷ 125 g"),
      ("ACEITE", 0.2, "~20 % de aceite (de girasol; parte es de oliva)"),
      ("ESTUCHE", 0.04, "Estuche de cartón de los packs"),
      ("FILM", 0.003, "Film de los packs"),
      ("CAJA", 0.04, "Caja de cartón"), PALE]),
    ("ACEITUNAS", "🫒", "Aceitunas de mesa", "Conservas", ["1039177001"],
     "Un tercio a granel para exportar; del resto, 40 % en lata, 30 % en tarro de vidrio y 30 % en bolsa "
     "(envases de ~350 g)",
     [("LATA", 0.77, "0,67 kg envasados × 40 % ÷ 350 g"),
      ("TARRO", 0.57, "0,67 kg × 30 % ÷ 350 g"),
      ("TAPA_METAL", 0.0046, "Tapa de ~8 g por tarro"),
      ("BOLSA_MULTICAPA", 0.005, "Bolsa de ~5 g por 200 g, en el 30 %"),
      ("ETIQUETA", 0.002, "Etiquetas"),
      ("CAJA", 0.03, "Caja de cartón"), PALE]),
    ("LEGUMBRES", "🫘", "Legumbres y hortalizas en conserva", "Conservas", ["1039179007"],
     "Tarro de vidrio de ~400 g con tapa (60 %) o lata (40 %)",
     [("TARRO", 1.5, "1 kg × 60 % ÷ 400 g"),
      ("TAPA_METAL", 0.012, "Tapa de ~8 g por tarro"),
      ("LATA", 1.0, "1 kg × 40 % ÷ 400 g"),
      ("ETIQUETA", 0.002, "Etiquetas"),
      ("CAJA", 0.03, "Caja de cartón"), PALE]),
    ("PLATOS", "🍲", "Platos preparados de carne", "Conservas", ["1085111003"],
     "40 % en lata o tarro de ~400 g; 60 % en bandeja con film y estuche",
     [("LATA", 1.0, "1 kg × 40 % ÷ 400 g"),
      ("BANDEJA", 0.03, "Bandeja de ~20 g por 400 g, en el 60 %"),
      ("FILM", 0.006, "Film de ~4 g por bandeja"),
      ("ESTUCHE", 0.02, "Estuche de cartón"),
      ("CAJA", 0.03, "Caja de cartón"), PALE]),
    ("MASCOTAS", "🐕", "Comida para perros y gatos", "Otros alimentos", ["1092103006"],
     "85 % pienso seco en saco de ~3 kg; 15 % comida húmeda en lata de 400 g",
     [("BOLSA_MULTICAPA", 0.013, "Saco de ~45 g por 3 kg, en el 85 %"),
      ("LATA", 0.375, "1 kg × 15 % ÷ 400 g"),
      ("CAJA", 0.02, "Caja de cartón"), PALE]),
    ("PAN", "🥖", "Pan fresco (barras, hogazas)", "Pan y bollería", ["1071110014"],
     "~62 % de harina; la mitad sale en bolsa de papel",
     [("HARINA", 0.62, "~620 g de harina por kg de pan"),
      ("BOLSA_PAPEL", 0.01, "Bolsa de ~5 g por barra de 250 g, en la mitad")]),
    ("BOLLERIA", "🥐", "Bollería y pastelería fresca", "Pan y bollería", ["1071120004"],
     "~45 % de harina; en bandeja con envoltorio y estuche",
     [("HARINA", 0.45, "~450 g de harina por kg"),
      ("BANDEJA", 0.02, "Bandeja de plástico"),
      ("FILM_BOPP", 0.012, "Envoltorio individual"),
      ("ESTUCHE", 0.03, "Estuche de cartón"),
      ("CAJA", 0.03, "Caja de cartón"), PALE]),
    ("GALLETAS", "🍪", "Galletas y pastas", "Pan y bollería", ["1072125507"],
     "~55 % de harina; en paquete de film con estuche de cartón",
     [("HARINA", 0.55, "~550 g de harina por kg"),
      ("FILM_BOPP", 0.02, "Paquetes de film"),
      ("ESTUCHE", 0.06, "Estuche de cartón"),
      ("CAJA", 0.03, "Caja de cartón"), PALE]),
    ("PIZZAS", "🍕", "Pizzas, empanadas y masas", "Pan y bollería", ["1072199006"],
     "~45 % de harina; con film y caja de cartón",
     [("HARINA", 0.45, "~450 g de harina por kg"),
      ("FILM", 0.012, "Film"),
      ("ESTUCHE", 0.06, "Caja de cartón de la pizza"),
      ("CAJA", 0.02, "Caja de transporte"), PALE]),
    ("CAFE", "☕", "Café tostado", "Otros alimentos", ["1083115009"],
     "Paquete multicapa de 250 g (~9 g); el café verde es importado y no está en la encuesta",
     [("BOLSA_MULTICAPA", 0.035, "Paquete de ~9 g por 250 g"),
      ("ESTUCHE", 0.02, "Estuches de cartón"),
      ("CAJA", 0.03, "Caja de cartón"), PALE]),
    ("DETERGENTE", "🧴", "Detergentes para la ropa y la vajilla", "Limpieza e higiene", ["2041325005"],
     "60 % líquido en botella de 3 l; 25 % en polvo en caja de cartón; 15 % en cápsulas en bolsa",
     [("GARRAFA", 0.19, "0,6 kg ÷ ~3,1 kg por botella"),
      ("TAPON", 0.003, "Tapón de ~15 g por botella"),
      ("ESTUCHE", 0.0125, "Caja de ~150 g por 3 kg de polvo, en el 25 %"),
      ("BOLSA_MULTICAPA", 0.0045, "Bolsa de las cápsulas"),
      ("ETIQUETA", 0.001, "Etiquetas"),
      ("CAJA", 0.03, "Caja de cartón"), PALE]),
    ("PAPEL_HIGIENICO", "🧻", "Papel higiénico", "Limpieza e higiene", ["1722112009"],
     "Rollo de ~110 g con canuto de cartón (~6 g), en paquete de film",
     [("TUBO_CARTON", 0.055, "Canuto de ~6 g por rollo de 110 g"),
      ("FILM", 0.02, "Bolsa de ~25 g por paquete de 12 rollos"), PALE]),
    ("PANALES", "👶", "Pañales y compresas", "Limpieza e higiene", ["1722123006"],
     "Paquete de plástico en caja de cartón",
     [("BOLSA", 0.025, "Bolsa de plástico del paquete"),
      ("CAJA", 0.03, "Caja de cartón"), PALE]),
    ("COLONIA", "🌸", "Colonias y aguas de tocador", "Limpieza e higiene", ["2042117009"],
     "Frasco de vidrio de ~250 ml de media, con tapón y estuche de cartón",
     [("FRASCO", 4, "1 l ÷ 250 ml"),
      ("TAPON", 0.02, "Tapón o pulverizador de ~5 g por frasco"),
      ("ESTUCHE", 0.16, "Estuche de ~40 g por frasco"),
      ("CAJA", 0.05, "Caja de cartón"), PALE]),
]

# Unidad de la encuesta -> (base de la receta, cuántas unidades base es una de la encuesta).
BASE = {
    "toneladas": ("kg", 1000),
    "kilogramos": ("kg", 1),
    "miles de litros": ("l", 1000),
    "hectolitros": ("l", 100),
}


def construir(datos: dict) -> dict:
    productos = {p["c"]: p for p in datos["productos"]}
    errores = []
    componentes = {}
    for alias, (codigo, nombre, unidad, factor) in COMPONENTES.items():
        if codigo not in productos:
            errores.append(f"Componente {alias}: el código {codigo} no está en la encuesta")
            continue
        componentes[alias] = {"c": codigo, "n": nombre, "u": unidad, "f": factor}
    recetas = []
    for rid, emoji, nombre, familia, codigos, formato, lista in RECETAS:
        bases = set()
        factores = {}
        for codigo in codigos:
            p = productos.get(codigo)
            if p is None:
                errores.append(f"Receta {rid}: el código {codigo} no está en la encuesta")
                continue
            if p["u"] not in BASE:
                errores.append(f"Receta {rid}: el producto {codigo} se mide en «{p['u']}»: no se sabe pasar a kg o l")
                continue
            base, factor = BASE[p["u"]]
            bases.add(base)
            factores[codigo] = factor
        if len(bases) > 1:
            errores.append(f"Receta {rid}: mezcla productos en kilos y en litros")
        for alias, cantidad, _nota in lista:
            if alias not in COMPONENTES:
                errores.append(f"Receta {rid}: componente desconocido {alias}")
            if cantidad <= 0:
                errores.append(f"Receta {rid}: cantidad no positiva para {alias}")
        recetas.append({
            "id": rid, "e": emoji, "n": nombre, "fam": familia, "fmt": formato,
            "base": bases.pop() if bases else "kg", "p": factores,
            "k": [{"a": a, "x": x, "nota": nota} for a, x, nota in lista],
        })
    if errores:
        raise ValueError("Errores en scripts/recetas.py:\n  " + "\n  ".join(errores))
    return {
        "meta": {"generado": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "componentes": componentes,
        "recetas": recetas,
    }


def generar(datos: dict) -> dict:
    """Comprueba las recetas contra produccion.json y escribe data/recetas.json."""
    resultado = construir(datos)
    temporal = SALIDA.with_suffix(".tmp")
    temporal.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(SALIDA)
    return resultado


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    datos = json.loads(PRODUCCION.read_text(encoding="utf-8"))
    resultado = generar(datos)
    print(f"Listo: {len(resultado['recetas'])} recetas con {len(resultado['componentes'])} componentes "
          f"→ {SALIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
