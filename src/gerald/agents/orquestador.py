"""GERALD-ORCH: decisión, política y pausas humanas (P02, P03, P04).

Los nodos con interrupt() no tienen efectos secundarios antes de la pausa, porque al reanudar
LangGraph vuelve a ejecutar el nodo desde el inicio. Las notificaciones previas las hace A4.
"""

from langgraph.types import interrupt

from gerald.decision import politica
from gerald.decision.decide import decide
from gerald.schemas.resultados import AceptacionCliente, AprobacionAdmin
from gerald.servicios import Servicios
from gerald.state import GeraldState

AGENTE = "orquestador"


def evaluar(state: GeraldState, servicios: Servicios) -> dict:
    """BPMN: Evaluar coherencia y nivel de confianza + ¿Coherente? + ¿Confianza alta y costo ≤ umbral?"""
    decision = decide(state["pedido"], state["boceto"], state["calculo"], servicios.evaluador)
    veredicto = politica.evaluar(decision, state["calculo"].costo_total_pen, servicios.parametros)
    servicios.pedidos.auditar(
        AGENTE,
        "veredicto",
        state["pedido"].pedido_id,
        {"decision": decision.model_dump(), "veredicto": veredicto.model_dump()},
    )
    salida: dict = {"decision": decision, "veredicto": veredicto}
    if veredicto.veredicto == "observar":
        salida["observaciones"] = decision.razones or [veredicto.motivo]
    return salida


def revision_admin(state: GeraldState, servicios: Servicios) -> dict:
    """BPMN: Revisar y aprobar propuesta (solo casos de excepción)."""
    respuesta = interrupt(
        {
            "tipo": "revision_admin",
            "pedido_id": state["pedido"].pedido_id,
            "motivo": state["veredicto"].motivo,
            "borrador": state["calculo"].model_dump(mode="json"),
        }
    )
    aprobacion = AprobacionAdmin.model_validate(respuesta)
    salida: dict = {"aprobacion_admin": aprobacion}
    if not aprobacion.aprobado:
        salida["observaciones"] = [aprobacion.comentario]
    return salida


def aceptacion_cliente(state: GeraldState, servicios: Servicios) -> dict:
    """BPMN: Aceptar cotización y contrato (1 clic)."""
    respuesta = interrupt(
        {
            "tipo": "aceptacion_cliente",
            "pedido_id": state["pedido"].pedido_id,
            "costo_total_pen": str(state["calculo"].costo_total_pen),
        }
    )
    return {"aceptacion_cliente": AceptacionCliente.model_validate(respuesta)}


def espera_abastecimiento(state: GeraldState, servicios: Servicios) -> dict:
    """BPMN: Abastecer material faltante (carril Almacén). Se reanuda al registrar el ingreso."""
    interrupt({"tipo": "abastecimiento", "pedido_id": state["pedido"].pedido_id})
    return {}
