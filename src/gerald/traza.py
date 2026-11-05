"""Traza del sistema multiagente: qué agente actuó, cuándo y qué produjo (gobernanza y portal).

Se reconstruye de los checkpoints de LangGraph: cada paso del grafo deja un checkpoint con el estado
resultante. No hay un registro paralelo que pueda desincronizarse.
"""

from collections.abc import Callable
from typing import Any

from gerald.graph import _config

# nodo → (agente, carril BPMN)
AGENTES: dict[str, tuple[str, str]] = {
    "a0_ingesta": ("A0 Ingesta", "sistema"),
    "a1_recepcion": ("A1 Recepción", "sistema"),
    "informar_duplicado": ("A4 Registro", "sistema"),
    "a2_boceto": ("A2 Boceto", "sistema"),
    "a3_calcular": ("A3 Materiales", "sistema"),
    "evaluar": ("Orquestador", "sistema"),
    "enviar_observaciones": ("A4 Registro", "sistema"),
    "solicitar_revision": ("A4 Registro", "sistema"),
    "revision_admin": ("Administrador", "humano"),
    "cotizar": ("A4 Registro", "sistema"),
    "aceptacion_cliente": ("Cliente", "humano"),
    "cerrar_no_contratado": ("A4 Registro", "sistema"),
    "registrar_contrato": ("A4 Registro", "sistema"),
    "verificar_stock": ("A3 Materiales", "sistema"),
    "requerir_abastecimiento": ("A3 Materiales", "sistema"),
    "espera_abastecimiento": ("Almacén", "humano"),
    "reservar": ("A3 Materiales", "sistema"),
    "generar_orden": ("A4 Registro", "sistema"),
    "notificar_confirmacion": ("A4 Registro", "sistema"),
}

ESPERANDO = {
    "revision_admin": "Esperando la revisión del administrador",
    "aceptacion_cliente": "Esperando que el cliente acepte la cotización",
    "espera_abastecimiento": "Esperando que el almacén abastezca el material faltante",
}


def _soles(valor: Any) -> str:
    return f"S/ {valor:,.2f}"


def _lista(valores: list[str]) -> str:
    return ", ".join(valores) if valores else "—"


def _a0(v: dict, det: bool) -> str:
    if v.get("estado") == "observado":
        return "Detectó datos por corregir: " + "; ".join(v.get("observaciones", []))
    lineas = v["pedido"].lineas
    return f"Validó el pedido: {len(lineas)} línea(s), {sum(li.cantidad for li in lineas)} prendas."


def _a1(v: dict, det: bool) -> str:
    if v.get("es_duplicado"):
        return "La clave SHA-256 ya existía: pedido duplicado, se descarta."
    clave = v.get("clave_idempotencia", "")
    return f"Generó la clave SHA-256 {clave[:12]}…, registró el pedido y confirmó la recepción."


def _a2(v: dict, det: bool) -> str:
    b = v.get("boceto")
    if b is None:
        return "No pudo leer el boceto: " + "; ".join(v.get("observaciones", []))
    if not b.legible:
        return "El boceto no permite identificar la prenda: " + "; ".join(b.observaciones or ["ilegible"])
    texto = f"Interpretó el boceto: {b.prenda}; colores {_lista(b.colores)}; elementos {_lista(b.elementos)}."
    return texto + (f" Confianza del agente: {b.confianza}." if det else "")


def _a3(v: dict, det: bool) -> str:
    c = v.get("calculo")
    if v.get("estado") == "observado" or c is None:
        return "No pudo calcular materiales: " + "; ".join(v.get("observaciones", []))
    materiales = ", ".join(f"{li.nombre} {li.cantidad} {li.unidad}" for li in c.lineas)
    return f"Calculó con el catálogo del almacén: {materiales}. Costo {_soles(c.costo_total_pen)}."


def _evaluar(v: dict, det: bool) -> str:
    d, ver = v.get("decision"), v.get("veredicto")
    if ver is None:
        return "Evaluó coherencia y confianza."
    accion = {
        "aprobar": "aprobación automática",
        "revision": "revisión del administrador",
        "observar": "observaciones al cliente",
    }[ver.veredicto]
    if not det:
        return f"Evaluó coherencia y confianza → {accion}."
    return (
        f"decide(): coherente={'sí' if d.coherente else 'no'}, puntaje {d.puntaje:.2f}. "
        f"Política determinista: confianza {ver.confianza} → {accion}. {ver.motivo}."
    )


def _revision(v: dict, det: bool) -> str:
    a = v.get("aprobacion_admin")
    if a is None:
        return "Revisión del administrador."
    return "Aprobó la propuesta." if a.aprobado else f"Rechazó la propuesta: {a.comentario}"


def _aceptacion(v: dict, det: bool) -> str:
    a = v.get("aceptacion_cliente")
    return "Aceptó la cotización y el contrato (1 clic)." if a and a.acepta else "No aceptó la cotización."


def _stock(v: dict, det: bool) -> str:
    return "Stock " + ("suficiente" if v.get("stock_suficiente") else "insuficiente") + " en el almacén."


def _reservar(v: dict, det: bool) -> str:
    r = v.get("reserva")
    if r and r.completa:
        return "Reservó los materiales en una transacción (SELECT … FOR UPDATE)."
    return "No pudo reservar todo: faltan materiales."


DETALLES: dict[str, Callable[[dict, bool], str]] = {
    "a0_ingesta": _a0,
    "a1_recepcion": _a1,
    "informar_duplicado": lambda v, d: "Informó al cliente que el pedido ya existe.",
    "a2_boceto": _a2,
    "a3_calcular": _a3,
    "evaluar": _evaluar,
    "enviar_observaciones": lambda v, d: "Envió al cliente las observaciones para corregir el pedido.",
    "solicitar_revision": lambda v, d: f"Escaló al administrador. {v['veredicto'].motivo}.",
    "revision_admin": _revision,
    "cotizar": lambda v, d: f"Generó y envió cotización y contrato: {_soles(v['calculo'].costo_total_pen)}.",
    "aceptacion_cliente": _aceptacion,
    "cerrar_no_contratado": lambda v, d: "Cerró el pedido como no contratado.",
    "registrar_contrato": lambda v, d: "Registró el contrato del pedido.",
    "verificar_stock": _stock,
    "requerir_abastecimiento": lambda v, d: "Generó el requerimiento de abastecimiento al almacén.",
    "espera_abastecimiento": lambda v, d: "Registró el ingreso del material faltante.",
    "reservar": _reservar,
    "generar_orden": lambda v, d: "Generó la lista de materiales y la orden de producción.",
    "notificar_confirmacion": lambda v, d: "Notificó al cliente y al administrador la fecha estimada.",
}


def traza(grafo: Any, pedido_id: str, detallado: bool) -> list[dict[str, Any]]:
    """Pasos del pedido en orden. `detallado` incluye puntajes internos (solo administrador)."""
    historia = list(grafo.get_state_history(_config(pedido_id)))[::-1]  # del más antiguo al último
    pasos: list[dict[str, Any]] = []
    for anterior, actual in zip(historia, historia[1:], strict=False):
        if (actual.metadata or {}).get("source") == "update":
            pasos.append(
                {
                    "nodo": "correccion",
                    "agente": "Corrección auditada",
                    "carril": "humano",
                    "estado": "hecho",
                    "momento": actual.created_at,
                    "detalle": "Se corrigió el estado del pedido; queda registrado en auditoría.",
                }
            )
            continue
        for nodo in anterior.next:
            if nodo not in AGENTES:
                continue
            agente, carril = AGENTES[nodo]
            try:
                detalle = DETALLES[nodo](actual.values, detallado)
            except (KeyError, AttributeError):
                detalle = "Paso completado."
            pasos.append(
                {
                    "nodo": nodo,
                    "agente": agente,
                    "carril": carril,
                    "estado": "hecho",
                    "momento": actual.created_at,
                    "detalle": detalle,
                }
            )
    if historia:
        for nodo in historia[-1].next:
            if nodo in AGENTES:
                agente, carril = AGENTES[nodo]
                pasos.append(
                    {
                        "nodo": nodo,
                        "agente": agente,
                        "carril": carril,
                        "estado": "esperando",
                        "momento": None,
                        "detalle": ESPERANDO.get(nodo, "En curso…"),
                    }
                )
    return pasos
