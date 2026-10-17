"""Contratos de salida de los agentes, decisiones y respuestas humanas (P02, P03, P04)."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Confianza = Literal["alta", "media", "baja"]


class ResultadoAgente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agente: str
    confianza: Confianza = "alta"
    evidencias: list[str] = []
    observaciones: list[str] = []


class InterpretacionBoceto(ResultadoAgente):
    agente: str = "a2_boceto"
    legible: bool
    prenda: str = Field(..., description="Tipo de prenda que muestra el boceto")
    colores: list[str] = []
    elementos: list[str] = Field(default=[], description="Logos, textos, números, estampados")


class Material(BaseModel):
    model_config = ConfigDict(frozen=True)

    material_id: str
    nombre: str
    tipo: Literal["tela", "insumo"]
    unidad: Literal["m", "m2", "kg", "und"]
    precio_unitario_pen: Decimal
    activo: bool = True


class LineaMaterial(BaseModel):
    material_id: str
    nombre: str
    unidad: str
    cantidad: Decimal
    precio_unitario_pen: Decimal
    subtotal_pen: Decimal


class CalculoMateriales(ResultadoAgente):
    agente: str = "a3_materiales"
    lineas: list[LineaMaterial] = []
    costo_total_pen: Decimal = Decimal("0")

    def requeridos(self) -> dict[str, Decimal]:
        return {linea.material_id: linea.cantidad for linea in self.lineas}


class Decision(BaseModel):
    """Salida de decide(): evalúa, no autoriza."""

    coherente: bool
    puntaje: float = Field(..., ge=0, le=1)
    confianza: Confianza
    razones: list[str] = []


class VeredictoPolitica(BaseModel):
    veredicto: Literal["aprobar", "revision", "observar"]
    confianza: Confianza
    motivo: str


class AprobacionAdmin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aprobado: bool
    comentario: str = ""

    @model_validator(mode="after")
    def _rechazo_con_comentario(self) -> "AprobacionAdmin":
        if not self.aprobado and not self.comentario.strip():
            raise ValueError("El rechazo requiere un comentario para el cliente")
        return self


class AceptacionCliente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acepta: bool


class Faltante(BaseModel):
    material_id: str
    cantidad: Decimal


class Reserva(ResultadoAgente):
    agente: str = "a3_materiales"
    completa: bool
    faltantes: list[Faltante] = []
