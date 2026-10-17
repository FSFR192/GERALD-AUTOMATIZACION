"""Tools del agente A3 Materiales (y solo de A3). Fuente: almacén de materiales (proveedores)."""

from decimal import Decimal

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from gerald.config import Parametros
from gerald.servicios import RepoAlmacen


class IdsMateriales(BaseModel):
    material_ids: list[str] = Field(..., min_length=1, max_length=50)


class PrendaTalla(BaseModel):
    prenda: str = Field(..., min_length=2, max_length=60)
    talla: str = Field(..., pattern=r"^(XS|S|M|L|XL|XXL)$")


class Cantidades(BaseModel):
    pedido_id: str = Field(..., min_length=3, max_length=40)
    cantidades: dict[str, Decimal] = Field(..., min_length=1, max_length=50)


class SinArgumentos(BaseModel):
    pass


def crear_tools_almacen(almacen: RepoAlmacen, parametros: Parametros | None = None) -> list[BaseTool]:
    @tool("leer_catalogo", args_schema=IdsMateriales)
    def leer_catalogo(material_ids: list[str]) -> list[dict]:
        """Devuelve nombre, tipo, unidad, precio y estado de los materiales del catálogo del almacén."""
        return [m.model_dump(mode="json") for m in almacen.materiales(material_ids).values()]

    @tool("leer_recetas", args_schema=PrendaTalla)
    def leer_recetas(prenda: str, talla: str) -> list[dict]:
        """Devuelve el consumo de cada material para una prenda y talla."""
        return [{"material_id": m, "cantidad": str(c)} for m, c in almacen.receta(prenda.lower(), talla)]

    @tool("consultar_stock", args_schema=IdsMateriales)
    def consultar_stock(material_ids: list[str]) -> dict[str, str]:
        """Devuelve el stock disponible por material en el almacén."""
        return {m: str(c) for m, c in almacen.stock(material_ids).items()}

    @tool("reservar_materiales", args_schema=Cantidades)
    def reservar_materiales(pedido_id: str, cantidades: dict[str, Decimal]) -> dict[str, str]:
        """Reserva materiales para el pedido en una transacción. Devuelve faltantes ({} = reservado)."""
        return {m: str(c) for m, c in almacen.reservar(pedido_id, cantidades).items()}

    @tool("crear_requerimiento_abastecimiento", args_schema=Cantidades)
    def crear_requerimiento_abastecimiento(pedido_id: str, cantidades: dict[str, Decimal]) -> str:
        """Registra un requerimiento de abastecimiento al almacén por los materiales faltantes."""
        almacen.crear_requerimiento(pedido_id, cantidades)
        return pedido_id

    @tool("leer_parametros", args_schema=SinArgumentos)
    def leer_parametros() -> dict:
        """Devuelve la merma y los umbrales vigentes de la política (solo lectura)."""
        return (parametros or Parametros()).model_dump(mode="json")

    return [
        leer_catalogo,
        leer_recetas,
        consultar_stock,
        reservar_materiales,
        crear_requerimiento_abastecimiento,
        leer_parametros,
    ]
