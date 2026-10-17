"""Gobernanza con LangSmith (P07): trazas por ejecución y por agente, sin datos personales.

Cada pedido es un hilo (`thread_id`) y cada nodo del grafo aparece como un paso con el nombre del
agente. Si el trazado está activo, entradas y salidas se ocultan salvo que se pida explícitamente lo
contrario: bocetos, correos y contratos nunca salen hacia LangSmith por defecto.
"""

import os


def configurar_trazas() -> bool:
    """Aplica valores seguros por defecto. Devuelve True si el trazado está activo."""
    activo = os.environ.get("LANGSMITH_TRACING", "").lower() == "true"
    if activo:
        os.environ.setdefault("LANGSMITH_HIDE_INPUTS", "true")
        os.environ.setdefault("LANGSMITH_HIDE_OUTPUTS", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", "gerald-sport")
    return activo


def metadatos_traza(pedido_id: str) -> dict:
    """Metadatos del run: solo el identificador del pedido (no es dato personal)."""
    return {"run_name": f"pedido {pedido_id}", "tags": ["gerald"], "metadata": {"pedido_id": pedido_id}}
