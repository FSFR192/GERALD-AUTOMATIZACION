"""Tools del agente A4 Registro (y solo de A4): correo con plantilla, hoja de materiales y contrato (P08)."""

import csv
import io
from typing import Any, Literal

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from gerald.schemas.resultados import CalculoMateriales, LineaMaterial
from gerald.servicios import Notificador, RepoPedidos

Evento = Literal[
    "recepcion",
    "observaciones",
    "duplicado",
    "revision",
    "cotizacion",
    "recordatorio",
    "abastecimiento",
    "confirmado",
    "alerta",
    "calibracion",
]


class EntradaCorreo(BaseModel):
    evento: Evento
    destinatario: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    pedido_id: str = Field(..., min_length=3, max_length=40)
    datos: dict[str, Any] = {}


class EntradaHoja(BaseModel):
    pedido_id: str = Field(..., min_length=3, max_length=40)
    lineas: list[LineaMaterial] = Field(..., min_length=1)


class EntradaContrato(BaseModel):
    pedido_id: str = Field(..., min_length=3, max_length=40)
    calculo: CalculoMateriales


def hoja_materiales(pedido_id: str, lineas: list[LineaMaterial]) -> str:
    """Lista de materiales de la orden de producción en CSV (se abre en cualquier hoja de cálculo)."""
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(["pedido", "material", "nombre", "unidad", "cantidad", "precio_pen", "subtotal_pen"])
    for li in lineas:
        escritor.writerow(
            [
                pedido_id,
                li.material_id,
                li.nombre,
                li.unidad,
                li.cantidad,
                li.precio_unitario_pen,
                li.subtotal_pen,
            ]
        )
    escritor.writerow([pedido_id, "TOTAL", "", "", "", "", sum(li.subtotal_pen for li in lineas)])
    return salida.getvalue()


def crear_tools_notificacion(notificador: Notificador, pedidos: RepoPedidos) -> list[BaseTool]:
    @tool("enviar_correo", args_schema=EntradaCorreo)
    def enviar_correo(evento: str, destinatario: str, pedido_id: str, datos: dict[str, Any]) -> str:
        """Envía un correo con la plantilla del evento. Idempotente por (pedido, evento, destinatario)."""
        notificador.enviar(evento, destinatario, pedido_id, datos)
        return "enviado"

    @tool("generar_hoja_materiales", args_schema=EntradaHoja)
    def generar_hoja_materiales(pedido_id: str, lineas: list[LineaMaterial]) -> str:
        """Genera la hoja (CSV) con la lista de materiales y el costo de la orden de producción."""
        return hoja_materiales(pedido_id, lineas)

    @tool("registrar_contrato", args_schema=EntradaContrato)
    def registrar_contrato(pedido_id: str, calculo: CalculoMateriales) -> str:
        """Registra el contrato aceptado del pedido con su cálculo de materiales. Idempotente."""
        pedidos.registrar_contrato(pedido_id, calculo)
        return pedido_id

    return [enviar_correo, generar_hoja_materiales, registrar_contrato]
