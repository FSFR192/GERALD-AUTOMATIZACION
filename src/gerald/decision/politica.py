"""Política determinista (P03). Código puro: sin LLM, sin red. Es la única que autoriza."""

from decimal import Decimal

from gerald.config import Parametros
from gerald.schemas.resultados import Confianza, Decision, VeredictoPolitica


def confianza_por_puntaje(puntaje: float, params: Parametros) -> Confianza:
    """La confianza se recalcula desde el puntaje; nunca se toma literal del LLM."""
    if puntaje >= params.puntaje_minimo_alta:
        return "alta"
    if puntaje >= params.puntaje_minimo_media:
        return "media"
    return "baja"


def evaluar(decision: Decision, costo_total_pen: Decimal, params: Parametros) -> VeredictoPolitica:
    if not decision.coherente:
        return VeredictoPolitica(
            veredicto="observar",
            confianza="baja",
            motivo="El boceto no es coherente con la prenda, las recetas o el costo",
        )

    confianza = confianza_por_puntaje(decision.puntaje, params)
    dentro_umbral = costo_total_pen <= params.umbral_costo_pen

    if confianza == "alta" and dentro_umbral:
        return VeredictoPolitica(
            veredicto="aprobar",
            confianza=confianza,
            motivo="Confianza alta y costo dentro del umbral",
        )

    motivos = []
    if confianza != "alta":
        motivos.append(f"confianza {confianza}")
    if not dentro_umbral:
        motivos.append(f"costo S/ {costo_total_pen} supera el umbral S/ {params.umbral_costo_pen}")
    return VeredictoPolitica(
        veredicto="revision",
        confianza=confianza,
        motivo="Revisión requerida: " + "; ".join(motivos),
    )
