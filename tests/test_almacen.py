"""Ruta 8: stock insuficiente → requerimiento → el almacén abastece → reserva y orden."""

from decimal import Decimal

from gerald.graph import ejecutar_pedido, reanudar
from tests.conftest import almacen_semilla


def test_faltante_abastecido_y_reservado(construir, nuevo_pedido):
    grafo, s = construir(almacen=almacen_semilla(dryfit="5"))
    pedido = nuevo_pedido(cantidad=10)  # requiere 12.96 m, hay 5
    ejecutar_pedido(grafo, pedido, s)
    r = reanudar(grafo, pedido.pedido_id, {"acepta": True}, s)

    assert r["pausa"]["tipo"] == "abastecimiento"
    req = s.almacen.requerimientos[0]
    assert req["faltantes"]["TEL-DRYFIT"] == Decimal("7.96")
    assert "abastecimiento" in s.notificador.eventos()

    s.almacen.ingresar("TEL-DRYFIT", Decimal("10"))  # única acción humana del almacén
    r = reanudar(grafo, pedido.pedido_id, None, s)
    assert r["estado"] == "en_produccion"
    assert s.almacen.disponible["TEL-DRYFIT"] == Decimal("2.04")


def test_abastecimiento_insuficiente_vuelve_a_requerir(construir, nuevo_pedido):
    grafo, s = construir(almacen=almacen_semilla(dryfit="5"))
    pedido = nuevo_pedido(cantidad=10)
    ejecutar_pedido(grafo, pedido, s)
    reanudar(grafo, pedido.pedido_id, {"acepta": True}, s)
    s.almacen.ingresar("TEL-DRYFIT", Decimal("1"))  # todavía falta
    r = reanudar(grafo, pedido.pedido_id, None, s)
    assert r["pausa"]["tipo"] == "abastecimiento"
    assert len(s.almacen.requerimientos) == 2
