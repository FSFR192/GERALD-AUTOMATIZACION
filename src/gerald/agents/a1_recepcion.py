"""A1 Recepción: clave de idempotencia, deduplicación y registro.
BPMN: Verificar si el pedido ya fue registrado / Registrar pedido y confirmar recepción.
"""

import hashlib
import json

from gerald.schemas.pedido import PedidoEntrada
from gerald.servicios import Servicios
from gerald.state import GeraldState

AGENTE = "a1_recepcion"


def clave_idempotencia(pedido: PedidoEntrada) -> str:
    """SHA-256 de cliente + boceto + líneas normalizadas. Mismo pedido ⇒ misma clave."""
    lineas = sorted(
        (linea.prenda.lower(), linea.talla, linea.color.lower(), linea.cantidad) for linea in pedido.lineas
    )
    base = json.dumps([pedido.cliente_id, pedido.boceto_sha256, lineas], separators=(",", ":"))
    return hashlib.sha256(base.encode()).hexdigest()


def nodo(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    clave = clave_idempotencia(pedido)

    existente = servicios.pedidos.existe_clave(clave)
    if existente and existente != pedido.pedido_id:
        return {"clave_idempotencia": clave, "es_duplicado": True, "estado": "duplicado"}

    if existente is None:  # si es este mismo pedido, es un reintento o reproceso: no se registra otra vez
        servicios.pedidos.registrar(pedido, clave)  # ErrorSistema si falla (P05)
        servicios.pedidos.auditar(AGENTE, "registrar_pedido", pedido.pedido_id, {"clave": clave})
    servicios.notificador.enviar(
        "recepcion",
        pedido.correo_cliente,
        pedido.pedido_id,
        {"lineas": [linea.model_dump() for linea in pedido.lineas]},
    )
    servicios.notificador.enviar("recepcion", servicios.correo_admin, pedido.pedido_id, {})
    return {"clave_idempotencia": clave, "es_duplicado": False, "estado": "recibido"}
