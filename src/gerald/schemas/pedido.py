"""Contrato de entrada del pedido (frontera de la API)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Talla = Literal["XS", "S", "M", "L", "XL", "XXL"]


class LineaPedido(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    prenda: str = Field(..., min_length=2, max_length=60, examples=["polo"])
    talla: Talla
    color: str = Field(..., min_length=2, max_length=40)
    cantidad: int = Field(..., ge=1, le=1000)


class DatosPedido(BaseModel):
    """Lo que envía el cliente junto al archivo del boceto."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    lineas: list[LineaPedido] = Field(..., min_length=1, max_length=50)
    notas: str | None = Field(default=None, max_length=500)


class PedidoEntrada(BaseModel):
    """Pedido completo tal como entra al grafo."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1.0"] = "1.0"
    pedido_id: str
    cliente_id: str
    correo_cliente: str
    boceto_uri: str
    boceto_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    lineas: list[LineaPedido] = Field(..., min_length=1)
    notas: str | None = None
