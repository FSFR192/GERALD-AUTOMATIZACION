"""@tool por agente (P06). Se construyen con fábricas que reciben solo el puerto que necesitan,
así cada agente recibe únicamente sus herramientas. Se usan cuando un agente opera en modo ReAct o
cuando se exponen por MCP (fase 4)."""

from langchain_core.tools import BaseTool

from gerald.servicios import Servicios


def tools_de(agente: str, servicios: Servicios) -> list[BaseTool]:
    """Único punto de entrega de tools: mínimo privilegio por agente (tabla de P06)."""
    from gerald.tools.almacen import crear_tools_almacen
    from gerald.tools.notificacion import crear_tools_notificacion
    from gerald.tools.recepcion import crear_tools_recepcion
    from gerald.tools.vision import crear_tools_vision

    if agente == "a1_recepcion":
        return crear_tools_recepcion(servicios.pedidos)
    if agente == "a2_boceto":
        return crear_tools_vision(servicios.interprete, servicios.ocr)
    if agente == "a3_materiales":
        return crear_tools_almacen(servicios.almacen, servicios.parametros)
    if agente == "a4_registro":
        return crear_tools_notificacion(servicios.notificador, servicios.pedidos)
    if agente == "orquestador":
        return [
            t
            for t in crear_tools_almacen(servicios.almacen, servicios.parametros)
            if t.name == "leer_parametros"
        ]
    return []
