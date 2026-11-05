"""Modo demo (GERALD_MODO=demo): API completa sin PostgreSQL ni Docker, con la semilla real en memoria.

Sin GERALD_GOOGLE_API_KEY no hay LLM: el boceto no se interpreta (se registra como dato) y la
evaluación usa las reglas fijas con confianza baja, así que TODO pedido pasa por el administrador.
Nunca hay aprobación automática sin modelo (regla 1).

Tokens de prueba:  uv run python -m gerald.demo cliente C-001
"""

import logging
import sys
import time

import jwt
from langgraph.checkpoint.memory import MemorySaver

from gerald.config import settings
from gerald.db import semilla
from gerald.db.memoria import AlmacenMemoria, NotificadorMemoria, PedidosMemoria
from gerald.decision.decide import reglas_fijas
from gerald.graph import construir_grafo, serializador
from gerald.schemas.pedido import PedidoEntrada
from gerald.schemas.resultados import InterpretacionBoceto
from gerald.servicios import Servicios

log = logging.getLogger("gerald.demo")


class InterpreteSinLLM:
    """Sin modelo de visión: toma la prenda declarada por el cliente y marca confianza baja."""

    def __call__(self, pedido: PedidoEntrada) -> InterpretacionBoceto:
        return InterpretacionBoceto(
            legible=True,
            prenda=pedido.lineas[0].prenda,
            confianza="baja",
            evidencias=["sin modelo de visión: boceto no interpretado"],
        )


class NotificadorConsola(NotificadorMemoria):
    def enviar(self, evento, destinatario, pedido_id, datos) -> None:
        super().enviar(evento, destinatario, pedido_id, datos)
        log.info("correo [%s] → %s · %s", evento, destinatario, pedido_id)


def construir_servicios_demo():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    cfg = settings()
    if cfg.google_api_key is not None or cfg.llm_proveedor == "ollama":
        from gerald.agents.a2_boceto import InterpreteVision, OcrVision
        from gerald.decision.decide import EvaluadorLLM

        interprete, evaluador, ocr = InterpreteVision(), EvaluadorLLM(), OcrVision()
    else:
        interprete, evaluador, ocr = InterpreteSinLLM(), reglas_fijas, None
        log.warning("Modo demo sin LLM: todos los pedidos irán a revisión del administrador.")
    servicios = Servicios(
        pedidos=PedidosMemoria(),
        almacen=AlmacenMemoria(semilla.MATERIALES, semilla.RECETAS, semilla.INVENTARIO),
        notificador=NotificadorConsola(),
        interprete=interprete,
        evaluador=evaluador,
        ocr=ocr,
        correo_admin=cfg.correo_admin,
        correo_almacen=cfg.correo_almacen,
    )
    return construir_grafo(servicios, MemorySaver(serde=serializador())), servicios


def token(rol: str, sub: str, correo: str | None = None, horas: int = 24) -> str:
    """JWT de desarrollo firmado con GERALD_JWT_SECRETO."""
    return jwt.encode(
        {"sub": sub, "rol": rol, "correo": correo or f"{sub.lower()}@demo.pe", "exp": int(time.time()) + horas * 3600},
        settings().jwt_secreto.get_secret_value(),
        algorithm="HS256",
    )


if __name__ == "__main__":
    rol = sys.argv[1] if len(sys.argv) > 1 else "cliente"
    sub = sys.argv[2] if len(sys.argv) > 2 else "C-001"
    correo = sys.argv[3] if len(sys.argv) > 3 else None
    print(token(rol, sub, correo))
