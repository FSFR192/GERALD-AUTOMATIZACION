"""A0 Ingesta: validación semántica del pedido. BPMN: Recibir y validar el pedido / ¿Datos completos?

La validación estructural ya ocurrió en la API (Pydantic). Aquí se revisan reglas de negocio
que producen observaciones accionables para el cliente.
"""

from gerald.servicios import Servicios
from gerald.state import GeraldState

AGENTE = "a0_ingesta"
MAX_PRENDAS_POR_PEDIDO = 5000


def nodo(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    observaciones: list[str] = []

    total = sum(linea.cantidad for linea in pedido.lineas)
    if total > MAX_PRENDAS_POR_PEDIDO:
        observaciones.append(
            f"El pedido suma {total} prendas; el máximo por pedido es {MAX_PRENDAS_POR_PEDIDO}. "
            "Divida el pedido en partes."
        )

    vistos = set()
    for linea in pedido.lineas:
        clave = (linea.prenda.lower(), linea.talla, linea.color.lower())
        if clave in vistos:
            observaciones.append(
                f"La línea {linea.prenda} talla {linea.talla} color {linea.color} está repetida; "
                "unifique las cantidades en una sola línea."
            )
        vistos.add(clave)

    if observaciones:
        return {"observaciones": observaciones, "estado": "observado"}
    return {"estado": "validado"}
