"""Modo demo sin LLM: nunca aprueba solo; todo pedido va al administrador (regla 1)."""

import os

from gerald.demo import construir_servicios_demo
from gerald.graph import ejecutar_pedido, reanudar
from gerald.observabilidad import configurar_trazas


def test_demo_sin_llm_siempre_va_a_revision(nuevo_pedido, monkeypatch):
    from gerald.config import settings

    monkeypatch.setattr(settings(), "google_api_key", None)
    monkeypatch.setattr(settings(), "llm_proveedor", "google")
    grafo, s = construir_servicios_demo()
    pedido = nuevo_pedido(prenda="short", talla="L", cantidad=4)
    r = ejecutar_pedido(grafo, pedido, s)
    assert r["pausa"]["tipo"] == "revision_admin"
    assert "confianza baja" in r["pausa"]["motivo"]
    r = reanudar(grafo, pedido.pedido_id, {"aprobado": True}, s)
    assert r["pausa"]["tipo"] == "aceptacion_cliente"
    assert reanudar(grafo, pedido.pedido_id, {"acepta": True}, s)["estado"] == "en_produccion"


def test_trazas_ocultan_datos_por_defecto(monkeypatch):
    for var in ("LANGSMITH_HIDE_INPUTS", "LANGSMITH_HIDE_OUTPUTS", "LANGSMITH_PROJECT"):
        monkeypatch.setenv(var, "x")  # registra la variable para que monkeypatch la restaure
        monkeypatch.delenv(var)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    assert configurar_trazas() is True
    assert os.environ["LANGSMITH_HIDE_INPUTS"] == "true"
    assert os.environ["LANGSMITH_HIDE_OUTPUTS"] == "true"


def test_clave_vacia_equivale_a_ausente():
    from gerald.config import Settings

    assert Settings(google_api_key="").google_api_key is None
    assert Settings(google_api_key="  ").google_api_key is None
