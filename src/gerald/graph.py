"""Construcción del StateGraph que implementa el BPMN TO-BE (ver docs/MAPEO-BPMN.md)."""

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy

from gerald.agents import (
    a0_ingesta,
    a1_recepcion,
    a2_boceto,
    a3_materiales,
    a4_registro,
    orquestador,
)
from gerald.errores import ErrorSistema, ErrorTransitorio
from gerald.observabilidad import metadatos_traza
from gerald.servicios import Servicios
from gerald.state import GeraldState

# Nodos que llevan RetryPolicy (todos menos las pausas humanas)
NODOS = {
    "a0_ingesta": a0_ingesta.nodo,
    "a1_recepcion": a1_recepcion.nodo,
    "informar_duplicado": a4_registro.informar_duplicado,
    "a2_boceto": a2_boceto.nodo,
    "a3_calcular": a3_materiales.calcular,
    "evaluar": orquestador.evaluar,
    "enviar_observaciones": a4_registro.enviar_observaciones,
    "solicitar_revision": a4_registro.solicitar_revision,
    "cotizar": a4_registro.cotizar,
    "cerrar_no_contratado": a4_registro.cerrar_no_contratado,
    "registrar_contrato": a4_registro.registrar_contrato,
    "verificar_stock": a3_materiales.verificar_stock,
    "requerir_abastecimiento": a3_materiales.requerir_abastecimiento,
    "reservar": a3_materiales.reservar,
    "generar_orden": a4_registro.generar_orden,
    "notificar_confirmacion": a4_registro.notificar_confirmacion,
}
PAUSAS = {
    "revision_admin": orquestador.revision_admin,
    "aceptacion_cliente": orquestador.aceptacion_cliente,
    "espera_abastecimiento": orquestador.espera_abastecimiento,
}


# ---------- condiciones de las compuertas ----------
def ruta_si_observado(siguiente: str):
    def ruta(state: GeraldState) -> str:
        return "enviar_observaciones" if state.get("estado") == "observado" else siguiente

    return ruta


def ruta_tras_recepcion(state: GeraldState) -> str:
    return "informar_duplicado" if state.get("es_duplicado") else "a2_boceto"


def ruta_tras_politica(state: GeraldState) -> str:
    return {
        "observar": "enviar_observaciones",
        "aprobar": "cotizar",
        "revision": "solicitar_revision",
    }[state["veredicto"].veredicto]


def ruta_tras_revision(state: GeraldState) -> str:
    return "cotizar" if state["aprobacion_admin"].aprobado else "enviar_observaciones"


def ruta_tras_aceptacion(state: GeraldState) -> str:
    return "registrar_contrato" if state["aceptacion_cliente"].acepta else "cerrar_no_contratado"


def ruta_tras_stock(state: GeraldState) -> str:
    return "reservar" if state["stock_suficiente"] else "requerir_abastecimiento"


def ruta_tras_reserva(state: GeraldState) -> str:
    return "generar_orden" if state["reserva"].completa else "requerir_abastecimiento"


# ---------- construcción ----------
def construir_grafo(servicios: Servicios, checkpointer: Any, reintento_inicial_s: float = 2.0):
    """Compila el grafo. En producción `checkpointer` es PostgresSaver; en pruebas MemorySaver."""
    reintentos = RetryPolicy(
        max_attempts=3,
        initial_interval=reintento_inicial_s,
        backoff_factor=2.0,
        retry_on=ErrorTransitorio,
    )
    g = StateGraph(GeraldState)

    def ligar(fn):
        return lambda state: fn(state, servicios)

    for nombre, fn in NODOS.items():
        g.add_node(nombre, ligar(fn), retry_policy=reintentos)
    for nombre, fn in PAUSAS.items():
        g.add_node(nombre, ligar(fn))

    g.add_edge(START, "a0_ingesta")
    g.add_conditional_edges(
        "a0_ingesta", ruta_si_observado("a1_recepcion"), ["enviar_observaciones", "a1_recepcion"]
    )
    g.add_conditional_edges("a1_recepcion", ruta_tras_recepcion, ["informar_duplicado", "a2_boceto"])
    g.add_edge("informar_duplicado", END)
    g.add_conditional_edges(
        "a2_boceto", ruta_si_observado("a3_calcular"), ["enviar_observaciones", "a3_calcular"]
    )
    g.add_conditional_edges("a3_calcular", ruta_si_observado("evaluar"), ["enviar_observaciones", "evaluar"])
    g.add_conditional_edges(
        "evaluar", ruta_tras_politica, ["enviar_observaciones", "cotizar", "solicitar_revision"]
    )
    g.add_edge("solicitar_revision", "revision_admin")
    g.add_conditional_edges("revision_admin", ruta_tras_revision, ["cotizar", "enviar_observaciones"])
    g.add_edge("enviar_observaciones", END)
    g.add_edge("cotizar", "aceptacion_cliente")
    g.add_conditional_edges(
        "aceptacion_cliente", ruta_tras_aceptacion, ["registrar_contrato", "cerrar_no_contratado"]
    )
    g.add_edge("cerrar_no_contratado", END)
    g.add_edge("registrar_contrato", "verificar_stock")
    g.add_conditional_edges("verificar_stock", ruta_tras_stock, ["reservar", "requerir_abastecimiento"])
    g.add_edge("requerir_abastecimiento", "espera_abastecimiento")
    g.add_edge("espera_abastecimiento", "verificar_stock")
    g.add_conditional_edges("reservar", ruta_tras_reserva, ["generar_orden", "requerir_abastecimiento"])
    g.add_edge("generar_orden", "notificar_confirmacion")
    g.add_edge("notificar_confirmacion", END)
    return g.compile(checkpointer=checkpointer)


# ---------- ejecución con manejo de errores por clase (P05) ----------
def _config(pedido_id: str) -> dict:
    return {"configurable": {"thread_id": pedido_id}, **metadatos_traza(pedido_id)}


def _ejecutar(grafo, entrada: Any, pedido_id: str, servicios: Servicios) -> dict:
    try:
        grafo.invoke(entrada, _config(pedido_id))
    except ErrorTransitorio as exc:  # reintentos agotados
        carga = grafo.get_state(_config(pedido_id)).values
        servicios.pedidos.encolar_pendiente(
            pedido_id, {k: _serializable(v) for k, v in carga.items()}, motivo=str(exc)
        )
        servicios.pedidos.actualizar_estado(pedido_id, "pendiente_reproceso")
        return {"estado": "pendiente_reproceso", "motivo": str(exc)}
    except ErrorSistema as exc:
        servicios.notificador.enviar(
            "alerta",
            servicios.correo_admin,
            pedido_id,
            {"origen": exc.origen, "error": exc.mensaje},
        )
        servicios.pedidos.actualizar_estado(pedido_id, "detenido")
        return {"estado": "detenido", "motivo": str(exc)}
    return resumen(grafo, pedido_id)


def ejecutar_pedido(grafo, pedido, servicios: Servicios) -> dict:
    """Entrada principal: procesa un pedido nuevo hasta terminar o hasta una pausa humana."""
    return _ejecutar(grafo, {"pedido": pedido, "observaciones": []}, pedido.pedido_id, servicios)


def reanudar(grafo, pedido_id: str, respuesta: dict | None, servicios: Servicios) -> dict:
    """Reanuda una pausa (revisión, aceptación o abastecimiento) con la respuesta humana."""
    valor = respuesta if respuesta is not None else {"continuar": True}  # {} no reanuda
    return _ejecutar(grafo, Command(resume=valor), pedido_id, servicios)


def reprocesar(grafo, pedido_id: str, servicios: Servicios) -> dict:
    """Reanuda desde el último checkpoint un pedido de la cola de pendientes."""
    return _ejecutar(grafo, None, pedido_id, servicios)


def resumen(grafo, pedido_id: str) -> dict:
    snap = grafo.get_state(_config(pedido_id))
    pausa = None
    if snap.tasks and snap.tasks[0].interrupts:
        pausa = snap.tasks[0].interrupts[0].value
    return {
        "estado": snap.values.get("estado"),
        "pausa": pausa,
        "observaciones": snap.values.get("observaciones", []),
    }


def _serializable(valor: Any) -> Any:
    if hasattr(valor, "model_dump"):
        return valor.model_dump(mode="json")
    return valor
