"""Rutas 2 y 4: datos inválidos / boceto ilegible / incoherente → observaciones al cliente."""

from gerald.graph import ejecutar_pedido
from tests.conftest import FakeEvaluador, FakeInterprete


def test_receta_inexistente_genera_observacion(construir, nuevo_pedido):
    grafo, s = construir()
    r = ejecutar_pedido(grafo, nuevo_pedido(talla="XXL"), s)
    assert r["estado"] == "observado"
    assert any("XXL" in o for o in r["observaciones"])
    assert "observaciones" in s.notificador.eventos()


def test_pedido_excede_maximo(construir, nuevo_pedido):
    grafo, s = construir()
    pedido = nuevo_pedido()
    pedido = pedido.model_copy(update={"lineas": pedido.lineas * 6})  # líneas repetidas
    r = ejecutar_pedido(grafo, pedido, s)
    assert r["estado"] == "observado"
    assert s.pedidos.claves == {}  # A0 corta antes de registrar


def test_boceto_ilegible(construir, nuevo_pedido):
    grafo, s = construir(interprete=FakeInterprete(legible=False))
    r = ejecutar_pedido(grafo, nuevo_pedido(), s)
    assert r["estado"] == "observado"


def test_boceto_incoherente(construir, nuevo_pedido):
    grafo, s = construir(evaluador=FakeEvaluador(coherente=False))
    r = ejecutar_pedido(grafo, nuevo_pedido(), s)
    assert r["estado"] == "observado"
    assert any("casaca" in o for o in r["observaciones"])
