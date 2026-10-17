"""Tools del agente A1 Recepción (y solo de A1): hash de idempotencia, búsqueda por clave y cola."""

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from gerald.agents.a1_recepcion import clave_idempotencia
from gerald.schemas.pedido import PedidoEntrada
from gerald.servicios import RepoPedidos


class EntradaPedido(BaseModel):
    pedido: PedidoEntrada


class EntradaClave(BaseModel):
    clave: str = Field(..., pattern=r"^[a-f0-9]{64}$")


class EntradaCola(BaseModel):
    pedido: PedidoEntrada
    motivo: str = Field(..., min_length=3, max_length=300)


def crear_tools_recepcion(pedidos: RepoPedidos) -> list[BaseTool]:
    @tool("calcular_hash", args_schema=EntradaPedido)
    def calcular_hash(pedido: PedidoEntrada) -> str:
        """Calcula la clave SHA-256 de idempotencia del pedido (cliente + boceto + líneas)."""
        return clave_idempotencia(pedido)

    @tool("buscar_pedido_por_clave", args_schema=EntradaClave)
    def buscar_pedido_por_clave(clave: str) -> str | None:
        """Devuelve el número del pedido ya registrado con esa clave, o null si es nuevo."""
        return pedidos.existe_clave(clave)

    @tool("encolar_pendiente", args_schema=EntradaCola)
    def encolar_pendiente(pedido: PedidoEntrada, motivo: str) -> str:
        """Guarda el pedido completo en la cola de pendientes para reproceso automático."""
        pedidos.encolar_pendiente(pedido.pedido_id, {"pedido": pedido.model_dump(mode="json")}, motivo)
        return pedido.pedido_id

    return [calcular_hash, buscar_pedido_por_clave, encolar_pendiente]
