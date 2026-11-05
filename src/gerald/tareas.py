"""Tareas programadas (cada 15 min): SLA de pausas humanas y reproceso de pendientes (P04, P05).

Ejecutar con cron/scheduler: `uv run python -m gerald.tareas` (cada 15 min) y
`uv run python -m gerald.tareas calibracion` (semanal).
Los temporizadores del BPMN viven aquí y no dentro del grafo.
"""

from gerald.calibracion import InformeCalibracion, informe
from gerald.graph import reanudar, reprocesar

SLA_ACEPTACION_CIERRE_HORAS = 96


def vigilar_sla(grafo, servicios) -> dict[str, list[str]]:
    p = servicios.parametros
    repo = servicios.pedidos
    hecho: dict[str, list[str]] = {"escalados": [], "recordados": [], "cerrados": []}

    for pedido_id in repo.vencidos("en_revision", p.sla_revision_horas):
        servicios.notificador.enviar(
            "recordatorio",
            servicios.correo_admin,
            pedido_id,
            {"motivo": "revisión pendiente > 24 h (escalado)"},
        )
        hecho["escalados"].append(pedido_id)

    for pedido_id in repo.vencidos("cotizado", SLA_ACEPTACION_CIERRE_HORAS):
        reanudar(grafo, pedido_id, {"acepta": False}, servicios)  # cierre: no contratado
        hecho["cerrados"].append(pedido_id)

    for pedido_id in repo.vencidos("cotizado", p.sla_aceptacion_horas):
        if pedido_id in hecho["cerrados"]:
            continue
        valores = grafo.get_state({"configurable": {"thread_id": pedido_id}}).values
        servicios.notificador.enviar("recordatorio", valores["pedido"].correo_cliente, pedido_id, {})
        hecho["recordados"].append(pedido_id)
    return hecho


def reprocesar_pendientes(grafo, servicios) -> dict[str, str]:
    """Reanuda desde el último checkpoint los pedidos de la cola de pendientes (P05).

    Recuperado → sale de la cola. Sigue fallando en el último intento → alerta y estado detenido.
    """
    maximo = servicios.parametros.max_reprocesos
    resultados: dict[str, str] = {}
    for pedido_id, intento in servicios.pedidos.tomar_pendientes(maximo):
        estado = reprocesar(grafo, pedido_id, servicios)["estado"]
        if estado != "pendiente_reproceso":
            servicios.pedidos.quitar_pendiente(pedido_id)
        elif intento >= maximo:
            servicios.notificador.enviar(
                "alerta",
                servicios.correo_admin,
                pedido_id,
                {"origen": "reproceso", "error": f"{maximo} reprocesos sin éxito"},
            )
            servicios.pedidos.actualizar_estado(pedido_id, "detenido")
            estado = "detenido"
        resultados[pedido_id] = estado
    return resultados


def calibracion_semanal(servicios, dias: int = 7) -> InformeCalibracion:
    """Informe confianza vs resultado; alerta de deriva al administrador (P03)."""
    resultado = informe(servicios.pedidos.etiquetas(dias), servicios.parametros, dias)
    if resultado.deriva:
        servicios.notificador.enviar(
            "calibracion",
            servicios.correo_admin,
            "calibracion",
            {"sugerencias": resultado.sugerencias},
        )
    servicios.pedidos.auditar("calibracion", "informe_semanal", "", resultado.model_dump(mode="json"))
    return resultado


if __name__ == "__main__":
    import sys

    from gerald.api.main import construir_servicios_produccion

    grafo, servicios = construir_servicios_produccion()
    if sys.argv[1:] == ["calibracion"]:
        print(calibracion_semanal(servicios).model_dump_json(indent=2))
    else:
        print(vigilar_sla(grafo, servicios))
        print(reprocesar_pendientes(grafo, servicios))
        reintentar = getattr(servicios.notificador, "reintentar_pendientes", None)
        if reintentar:
            print({"correos_reenviados": reintentar()})
