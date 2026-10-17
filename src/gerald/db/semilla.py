"""Datos semilla del almacén (libro de reglas): única fuente para PostgreSQL y el modo en memoria.

7 materiales · 14 recetas (prenda × talla) · inventario inicial · parámetros de la política (P03).
"""

from decimal import Decimal

from gerald.schemas.resultados import Material

D = Decimal

MATERIALES: list[Material] = [
    Material(
        material_id="TEL-DRYFIT",
        nombre="Tela dry-fit",
        tipo="tela",
        unidad="m",
        precio_unitario_pen=D("12.50"),
    ),
    Material(
        material_id="TEL-ALGODON",
        nombre="Tela algodón jersey",
        tipo="tela",
        unidad="m",
        precio_unitario_pen=D("9.80"),
    ),
    Material(
        material_id="TEL-MICRO",
        nombre="Tela microfibra impermeable",
        tipo="tela",
        unidad="m",
        precio_unitario_pen=D("18.00"),
    ),
    Material(
        material_id="INS-HILO",
        nombre="Hilo poliéster (cono)",
        tipo="insumo",
        unidad="und",
        precio_unitario_pen=D("0.40"),
    ),
    Material(
        material_id="INS-SUBLIM",
        nombre="Papel de sublimación",
        tipo="insumo",
        unidad="m2",
        precio_unitario_pen=D("3.20"),
    ),
    Material(
        material_id="INS-ELAST",
        nombre="Elástico de cintura",
        tipo="insumo",
        unidad="m",
        precio_unitario_pen=D("1.10"),
    ),
    Material(
        material_id="INS-CIERRE",
        nombre="Cierre metálico",
        tipo="insumo",
        unidad="und",
        precio_unitario_pen=D("2.50"),
    ),
]

# Consumo por prenda y talla, antes de merma. Clave: (prenda, talla).
RECETAS: dict[tuple[str, str], list[tuple[str, Decimal]]] = {
    **{
        ("polo", t): [("TEL-DRYFIT", D(tela)), ("INS-HILO", D("1")), ("INS-SUBLIM", D(sub))]
        for t, tela, sub in [
            ("XS", "1.00", "0.55"),
            ("S", "1.10", "0.60"),
            ("M", "1.20", "0.65"),
            ("L", "1.30", "0.70"),
            ("XL", "1.40", "0.75"),
            ("XXL", "1.50", "0.80"),
        ]
    },
    **{
        ("short", t): [("TEL-DRYFIT", D(tela)), ("INS-HILO", D("1")), ("INS-ELAST", D(elast))]
        for t, tela, elast in [
            ("S", "0.60", "0.70"),
            ("M", "0.65", "0.80"),
            ("L", "0.70", "0.90"),
            ("XL", "0.75", "1.00"),
        ]
    },
    **{
        ("casaca", t): [("TEL-MICRO", D(tela)), ("INS-HILO", D("2")), ("INS-CIERRE", D("1"))]
        for t, tela in [("S", "1.60"), ("M", "1.75"), ("L", "1.90"), ("XL", "2.05")]
    },
}

INVENTARIO: dict[str, Decimal] = {
    "TEL-DRYFIT": D("200"),
    "TEL-ALGODON": D("150"),
    "TEL-MICRO": D("80"),
    "INS-HILO": D("500"),
    "INS-SUBLIM": D("120"),
    "INS-ELAST": D("150"),
    "INS-CIERRE": D("100"),
}

PARAMETROS: dict[str, str] = {
    "umbral_costo_pen": "300.00",
    "merma_pct": "8",
    "puntaje_minimo_alta": "0.85",
    "puntaje_minimo_media": "0.60",
    "sla_revision_horas": "24",
    "sla_aceptacion_horas": "48",
    "max_reprocesos": "3",
}
