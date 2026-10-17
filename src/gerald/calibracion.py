"""Bucle de calibración (P03): confianza vs resultado real → sugerencias de umbral y alerta de deriva.

Las sugerencias son borradores para el administrador: nunca modifican `parametros` por sí solas.
"""

from typing import Any

from pydantic import BaseModel

from gerald.config import Parametros

TASA_MAXIMA_RECHAZO_ALTA = 0.05  # P03: deriva si > 5 % de pedidos con confianza alta fracasan
MUESTRA_MINIMA = 20
RESULTADOS_FALLIDOS = {"observado", "no_contratado"}


class Tramo(BaseModel):
    pedidos: int
    contratados: int
    fallidos: int
    tasa_fallo: float


class InformeCalibracion(BaseModel):
    dias: int
    total: int
    por_confianza: dict[str, Tramo]
    deriva: bool
    sugerencias: list[str]


def _fallido(etiqueta: dict[str, Any]) -> bool:
    return etiqueta.get("resultado") in RESULTADOS_FALLIDOS or etiqueta.get("aprobado_admin") is False


def informe(etiquetas: list[dict[str, Any]], params: Parametros, dias: int = 7) -> InformeCalibracion:
    tramos: dict[str, Tramo] = {}
    for nivel in ("alta", "media", "baja"):
        grupo = [e for e in etiquetas if e.get("confianza") == nivel]
        fallidos = sum(_fallido(e) for e in grupo)
        tramos[nivel] = Tramo(
            pedidos=len(grupo),
            contratados=sum(e.get("resultado") == "contratado" for e in grupo),
            fallidos=fallidos,
            tasa_fallo=round(fallidos / len(grupo), 4) if grupo else 0.0,
        )

    alta, media = tramos["alta"], tramos["media"]
    deriva = alta.pedidos >= MUESTRA_MINIMA and alta.tasa_fallo > TASA_MAXIMA_RECHAZO_ALTA
    sugerencias: list[str] = []
    if deriva:
        nuevo = min(round(params.puntaje_minimo_alta + 0.05, 2), 0.95)
        sugerencias.append(
            f"Deriva: {alta.tasa_fallo:.0%} de los pedidos con confianza alta fracasaron "
            f"(máximo {TASA_MAXIMA_RECHAZO_ALTA:.0%}). Subir puntaje_minimo_alta de "
            f"{params.puntaje_minimo_alta} a {nuevo} y revisar las recetas de esos pedidos."
        )
    elif media.pedidos >= MUESTRA_MINIMA and media.tasa_fallo <= TASA_MAXIMA_RECHAZO_ALTA:
        nuevo = max(round(params.puntaje_minimo_alta - 0.05, 2), params.puntaje_minimo_media + 0.05)
        sugerencias.append(
            f"Los pedidos con confianza media se aprueban casi siempre ({1 - media.tasa_fallo:.0%}). "
            f"Puede bajar puntaje_minimo_alta de {params.puntaje_minimo_alta} a {nuevo} "
            "para reducir revisiones del administrador."
        )
    if alta.pedidos < MUESTRA_MINIMA:
        sugerencias.append(
            f"Muestra insuficiente de confianza alta ({alta.pedidos} < {MUESTRA_MINIMA}); sin conclusión."
        )
    return InformeCalibracion(
        dias=dias, total=len(etiquetas), por_confianza=tramos, deriva=deriva, sugerencias=sugerencias
    )
