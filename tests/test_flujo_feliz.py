"""Ruta 1: aprobación automática, aceptación del cliente, stock suficiente, orden y notificación."""

from decimal import Decimal

from gerald.graph import ejecutar_pedido, reanudar


def test_camino_feliz_solo_un_clic_del_cliente(construir, nuevo_pedido):
    grafo, s = construir()
    pedido = nuevo_pedido(cantidad=10)  # 10 polos M ≈ S/ 166 < S/ 300

    r = ejecutar_pedido(grafo, pedido, s)
    assert r["pausa"]["tipo"] == "aceptacion_cliente"  # el admin NO intervino

    r = reanudar(grafo, pedido.pedido_id, {"acepta": True}, s)
    assert r["estado"] == "en_produccion"
    assert pedido.pedido_id in s.almacen.reservas
    assert s.almacen.reservas[pedido.pedido_id]["TEL-DRYFIT"] == Decimal(
        "12.96"
    )  # 1.2 m × 10 × 1.08 de merma
    eventos = s.notificador.eventos()
    assert eventos[0] == "recepcion" and "cotizacion" in eventos and eventos[-1] == "confirmado"
    assert "revision" not in eventos
    assert s.pedidos.etiquetas_registradas[-1]["resultado"] == "contratado"
