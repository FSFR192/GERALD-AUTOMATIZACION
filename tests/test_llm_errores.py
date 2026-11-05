"""P05 en la frontera del LLM: todo error del proveedor se traduce a una clase conocida."""

import pytest

from gerald.errores import ErrorSistema, ErrorTransitorio
from gerald.llm import invocar_con_errores


class ModeloQueFalla:
    def __init__(self, exc):
        self.exc = exc

    def invoke(self, mensajes):
        raise self.exc


@pytest.mark.parametrize(
    ("mensaje", "clase"),
    [
        ("503 UNAVAILABLE", ErrorTransitorio),
        ("429 rate limit", ErrorTransitorio),
        ("403 PERMISSION_DENIED api key", ErrorSistema),
        ("404 NOT_FOUND. models/gemini-2.5-flash is no longer available", ErrorSistema),
        ("504 DEADLINE_EXCEEDED", ErrorTransitorio),
        ("algo totalmente inesperado", ErrorSistema),
    ],
)
def test_errores_del_modelo_se_clasifican(mensaje, clase):
    with pytest.raises(clase):
        invocar_con_errores(ModeloQueFalla(RuntimeError(mensaje)), [], "a2_boceto")


def test_modelo_retirado_detiene_y_alerta(construir, nuevo_pedido):
    from gerald.graph import ejecutar_pedido
    from tests.conftest import FakeInterprete

    error = ErrorSistema("a2_boceto", "el modelo configurado no existe o fue retirado")
    grafo, s = construir(interprete=FakeInterprete(error=error))
    r = ejecutar_pedido(grafo, nuevo_pedido(), s)
    assert r["estado"] == "detenido"
    assert s.notificador.enviados[-1]["evento"] == "alerta"


def test_timeout_sin_mensaje_es_transitorio():
    class ReadTimeout(Exception):
        pass

    with pytest.raises(ErrorTransitorio):
        invocar_con_errores(ModeloQueFalla(ReadTimeout()), [], "a2_boceto")
