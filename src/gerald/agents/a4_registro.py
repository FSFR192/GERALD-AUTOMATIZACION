"""A4 Registro y notificación (P08).
BPMN: Informar duplicado / Enviar observaciones / Generar y enviar cotización / Registrar contrato /
Generar lista de materiales y orden de producción / Notificar fecha estimada.
"""

from datetime import date, timedelta

from gerald.servicios import Servicios
from gerald.state import GeraldState
from gerald.tools.notificacion import hoja_materiales

AGENTE = "a4_registro"
DIAS_PRODUCCION = 7


def informar_duplicado(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    servicios.notificador.enviar("duplicado", pedido.correo_cliente, pedido.pedido_id, {})
    return {}


def enviar_observaciones(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    observaciones = list(dict.fromkeys(state.get("observaciones", [])))  # sin repetidos
    servicios.notificador.enviar(
        "observaciones", pedido.correo_cliente, pedido.pedido_id, {"observaciones": observaciones}
    )
    servicios.pedidos.actualizar_estado(pedido.pedido_id, "observado")
    _etiquetar(state, servicios, resultado="observado")
    return {"estado": "observado"}


def solicitar_revision(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    servicios.notificador.enviar(
        "revision", servicios.correo_admin, pedido.pedido_id, {"motivo": state["veredicto"].motivo}
    )
    servicios.pedidos.actualizar_estado(pedido.pedido_id, "en_revision")
    return {"estado": "en_revision"}


def cotizar(state: GeraldState, servicios: Servicios) -> dict:
    pedido, calculo = state["pedido"], state["calculo"]
    servicios.notificador.enviar(
        "cotizacion",
        pedido.correo_cliente,
        pedido.pedido_id,
        {
            "costo_total_pen": str(calculo.costo_total_pen),
            "lineas": [linea.model_dump(mode="json") for linea in pedido.lineas],
        },
    )
    servicios.pedidos.actualizar_estado(pedido.pedido_id, "cotizado")
    return {"estado": "cotizado"}


def registrar_contrato(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    servicios.pedidos.registrar_contrato(pedido.pedido_id, state["calculo"])
    servicios.pedidos.auditar(AGENTE, "registrar_contrato", pedido.pedido_id, {})
    servicios.pedidos.actualizar_estado(pedido.pedido_id, "contratado")
    return {"estado": "contratado"}


def cerrar_no_contratado(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    servicios.pedidos.actualizar_estado(pedido.pedido_id, "no_contratado")
    _etiquetar(state, servicios, resultado="no_contratado")
    return {"estado": "no_contratado"}


def generar_orden(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    servicios.pedidos.auditar(
        AGENTE,
        "generar_orden_produccion",
        pedido.pedido_id,
        {"materiales": [linea.model_dump(mode="json") for linea in state["calculo"].lineas]},
    )
    servicios.pedidos.actualizar_estado(pedido.pedido_id, "en_produccion")
    return {"estado": "en_produccion"}


def notificar_confirmacion(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    fecha = (date.today() + timedelta(days=DIAS_PRODUCCION)).isoformat()
    servicios.notificador.enviar(
        "confirmado", pedido.correo_cliente, pedido.pedido_id, {"fecha_estimada": fecha}
    )
    servicios.notificador.enviar(
        "confirmado",
        servicios.correo_admin,
        pedido.pedido_id,
        {
            "fecha_estimada": fecha,
            "lista_materiales": hoja_materiales(pedido.pedido_id, state["calculo"].lineas),
        },
    )
    _etiquetar(state, servicios, resultado="contratado")
    return {}


def _etiquetar(state: GeraldState, servicios: Servicios, resultado: str) -> None:
    """Bucle de calibración (P03): decisión vs resultado real."""
    decision, veredicto = state.get("decision"), state.get("veredicto")
    aprob = state.get("aprobacion_admin")
    servicios.pedidos.registrar_etiqueta(
        state["pedido"].pedido_id,
        {
            "puntaje": decision.puntaje if decision else None,
            "confianza": veredicto.confianza if veredicto else None,
            "veredicto": veredicto.veredicto if veredicto else None,
            "aprobado_admin": aprob.aprobado if aprob else None,
            "resultado": resultado,
        },
    )
