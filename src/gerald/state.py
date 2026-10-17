"""Estado compartido del grafo (P01). Una clave, un escritor; `observaciones` es acumulativa."""

import operator
from typing import Annotated, Literal, TypedDict

from gerald.schemas.pedido import PedidoEntrada
from gerald.schemas.resultados import (
    AceptacionCliente,
    AprobacionAdmin,
    CalculoMateriales,
    Decision,
    InterpretacionBoceto,
    Reserva,
    VeredictoPolitica,
)

EstadoPedido = Literal[
    "recibido",
    "validado",
    "interpretado",
    "calculado",
    "en_revision",
    "cotizado",
    "contratado",
    "esperando_abastecimiento",
    "reservado",
    "en_produccion",
    "observado",
    "duplicado",
    "no_contratado",
    "pendiente_reproceso",
    "detenido",
]


class GeraldState(TypedDict, total=False):
    pedido: PedidoEntrada  # API
    clave_idempotencia: str  # A1
    es_duplicado: bool  # A1
    boceto: InterpretacionBoceto  # A2
    calculo: CalculoMateriales  # A3
    decision: Decision  # orquestador (decide)
    veredicto: VeredictoPolitica  # orquestador (política)
    aprobacion_admin: AprobacionAdmin  # HITL administrador
    aceptacion_cliente: AceptacionCliente  # HITL cliente
    stock_suficiente: bool  # A3
    reserva: Reserva  # A3
    observaciones: Annotated[list[str], operator.add]
    estado: EstadoPedido  # nodo que cambia de etapa
