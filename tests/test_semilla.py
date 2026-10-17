"""Libro de reglas: la semilla del almacén es coherente (7 materiales, 14 recetas) y calcula costos."""

from decimal import Decimal

from gerald.config import Parametros
from gerald.db import semilla
from gerald.db.memoria import AlmacenMemoria
from gerald.graph import ejecutar_pedido


def test_semilla_coherente():
    ids = {m.material_id for m in semilla.MATERIALES}
    assert len(ids) == 7
    assert len(semilla.RECETAS) == 14
    assert {mid for receta in semilla.RECETAS.values() for mid, _ in receta} <= ids
    assert set(semilla.INVENTARIO) == ids
    assert set(semilla.PARAMETROS) <= set(Parametros.model_fields)


def test_parametros_desde_tabla_se_tipan():
    p = Parametros.model_validate(semilla.PARAMETROS)
    assert p.umbral_costo_pen == Decimal("300.00")
    assert p.puntaje_minimo_alta == 0.85
    assert p.max_reprocesos == 3


def test_casaca_con_semilla_real(construir, nuevo_pedido):
    from tests.conftest import FakeInterprete

    almacen = AlmacenMemoria(semilla.MATERIALES, semilla.RECETAS, semilla.INVENTARIO)
    grafo, s = construir(almacen=almacen, interprete=FakeInterprete(prenda="casaca"))
    r = ejecutar_pedido(grafo, nuevo_pedido(prenda="casaca", talla="M", cantidad=5), s)
    # 5 × 1.75 m × 1.08 = 9.45 m × 18 = 170.10; hilo 10.8 → 11 und × 0.40 = 4.40;
    # cierre 5.4 → 6 und × 2.50 = 15.00 (las unidades enteras se redondean hacia arriba)
    assert r["pausa"]["tipo"] == "aceptacion_cliente"
    assert r["pausa"]["costo_total_pen"] == "189.50"
    calculo = grafo.get_state({"configurable": {"thread_id": r["pausa"]["pedido_id"]}}).values["calculo"]
    cantidades = {li.material_id: li.cantidad for li in calculo.lineas}
    assert cantidades == {"TEL-MICRO": Decimal("9.45"), "INS-HILO": Decimal("11"), "INS-CIERRE": Decimal("6")}
