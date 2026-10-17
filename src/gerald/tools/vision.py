"""Tools del agente A2 Boceto (y solo de A2): interpretación visual y OCR del boceto.

Lo que devuelven es dato del cliente: nunca se interpola en un prompt de sistema (regla 6).
"""

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel

from gerald.errores import ErrorSistema
from gerald.schemas.pedido import PedidoEntrada
from gerald.servicios import InterpreteBoceto, Ocr


class EntradaBoceto(BaseModel):
    pedido: PedidoEntrada


def crear_tools_vision(interprete: InterpreteBoceto, ocr: Ocr | None) -> list[BaseTool]:
    @tool("interpretar_boceto", args_schema=EntradaBoceto)
    def interpretar_boceto(pedido: PedidoEntrada) -> dict:
        """Describe el boceto: tipo de prenda, colores y elementos (logos, textos, números)."""
        return interprete(pedido).model_dump(mode="json")

    @tool("extraer_texto_ocr", args_schema=EntradaBoceto)
    def extraer_texto_ocr(pedido: PedidoEntrada) -> list[str]:
        """Transcribe los textos y números visibles en el boceto (nombres, dorsales, lemas)."""
        if ocr is None:
            raise ErrorSistema("a2_boceto", "OCR no configurado")
        return ocr(pedido)

    return [interpretar_boceto, extraer_texto_ocr]
