"""Rutas 5 y 6: revisión del administrador solo por excepción."""

import pytest
from pydantic import ValidationError

from gerald.graph import ejecutar_pedido, reanudar
from tests.conftest import FakeEvaluador


def test_costo_alto_va_a_revision_y_se_aprueba(construir, nuevo_pedido):
    grafo, s = construir()
    pedido = nuevo_pedido(cantidad=30)  # ≈ S/ 499 > S/ 300
    r = ejecutar_pedido(grafo, pedido, s)
    assert r["pausa"]["tipo"] == "revision_admin"
    assert "umbral" in r["pausa"]["motivo"]
    r = reanudar(grafo, pedido.pedido_id, {"aprobado": True}, s)
    assert r["pausa"]["tipo"] == "aceptacion_cliente"


def test_confianza_media_rechazada_genera_observacion(construir, nuevo_pedido):
    grafo, s = construir(evaluador=FakeEvaluador(puntaje=0.7))
    pedido = nuevo_pedido()
    ejecutar_pedido(grafo, pedido, s)
    r = reanudar(
        grafo,
        pedido.pedido_id,
        {"aprobado": False, "comentario": "El logo debe ir en el pecho izquierdo"},
        s,
    )
    assert r["estado"] == "observado"
    assert "El logo debe ir en el pecho izquierdo" in r["observaciones"]


def test_rechazo_sin_comentario_no_se_acepta(construir, nuevo_pedido):
    grafo, s = construir(evaluador=FakeEvaluador(puntaje=0.7))
    pedido = nuevo_pedido()
    ejecutar_pedido(grafo, pedido, s)
    with pytest.raises(ValidationError):
        reanudar(grafo, pedido.pedido_id, {"aprobado": False}, s)
