"""Ruta 7 y SLA: el cliente no acepta → pedido no contratado; recordatorios por SLA."""

from datetime import UTC, datetime, timedelta

from gerald.graph import ejecutar_pedido, reanudar
from gerald.tareas import vigilar_sla


def test_cliente_no_acepta(construir, nuevo_pedido):
    grafo, s = construir()
    pedido = nuevo_pedido()
    ejecutar_pedido(grafo, pedido, s)
    r = reanudar(grafo, pedido.pedido_id, {"acepta": False}, s)
    assert r["estado"] == "no_contratado"
    assert s.almacen.reservas == {}
    assert s.pedidos.etiquetas_registradas[-1]["resultado"] == "no_contratado"


def test_sla_recordatorio_y_cierre(construir, nuevo_pedido):
    grafo, s = construir()
    p1, p2 = nuevo_pedido(cantidad=5), nuevo_pedido(cantidad=6)
    ejecutar_pedido(grafo, p1, s)
    ejecutar_pedido(grafo, p2, s)
    ahora = datetime.now(UTC)
    s.pedidos.pedidos[p1.pedido_id]["cambio"] = ahora - timedelta(hours=50)  # > 48 h
    s.pedidos.pedidos[p2.pedido_id]["cambio"] = ahora - timedelta(hours=100)  # > 96 h

    hecho = vigilar_sla(grafo, s)
    assert hecho["recordados"] == [p1.pedido_id]
    assert hecho["cerrados"] == [p2.pedido_id]
    assert s.pedidos.pedidos[p2.pedido_id]["estado"] == "no_contratado"
