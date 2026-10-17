"""Ruta 3: el mismo pedido enviado dos veces se descarta sin nuevo registro."""

from gerald.graph import ejecutar_pedido


def test_pedido_duplicado(construir, nuevo_pedido):
    grafo, s = construir()
    ejecutar_pedido(grafo, nuevo_pedido(), s)
    r = ejecutar_pedido(grafo, nuevo_pedido(), s)  # mismo contenido, otro pedido_id
    assert r["estado"] == "duplicado"
    assert len(s.pedidos.claves) == 1
    assert s.notificador.eventos().count("duplicado") == 1
