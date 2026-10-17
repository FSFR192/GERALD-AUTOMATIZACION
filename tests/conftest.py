"""Fixtures: almacén semilla, dobles de LLM y grafo con MemorySaver. Nunca se llama a un LLM real."""

import uuid
from decimal import Decimal

import pytest
from langgraph.checkpoint.memory import MemorySaver

from gerald.db.memoria import AlmacenMemoria, NotificadorMemoria, PedidosMemoria
from gerald.graph import construir_grafo
from gerald.schemas.pedido import LineaPedido, PedidoEntrada
from gerald.schemas.resultados import Decision, InterpretacionBoceto, Material
from gerald.servicios import Servicios

D = Decimal


class FakeInterprete:
    def __init__(self, prenda: str = "polo", legible: bool = True, error: Exception | None = None):
        self.prenda, self.legible, self.error, self.llamadas = prenda, legible, error, 0

    def __call__(self, pedido):
        self.llamadas += 1
        if self.error:
            raise self.error
        return InterpretacionBoceto(
            legible=self.legible, prenda=self.prenda, colores=["azul"], elementos=["logo frontal"]
        )


class FakeEvaluador:
    def __init__(self, coherente: bool = True, puntaje: float = 0.95):
        self.coherente, self.puntaje = coherente, puntaje

    def __call__(self, pedido, boceto, calculo):
        return Decision(
            coherente=self.coherente,
            puntaje=self.puntaje,
            confianza="alta",
            razones=[] if self.coherente else ["El boceto muestra una casaca, no un polo"],
        )


def almacen_semilla(dryfit: str = "200") -> AlmacenMemoria:
    materiales = [
        Material(
            material_id="TEL-DRYFIT",
            nombre="Tela dry-fit",
            tipo="tela",
            unidad="m",
            precio_unitario_pen=D("12.50"),
        ),
        Material(
            material_id="INS-HILO",
            nombre="Hilo",
            tipo="insumo",
            unidad="und",
            precio_unitario_pen=D("0.40"),
        ),
    ]
    recetas = {
        (p, t): [("TEL-DRYFIT", D("1.2")), ("INS-HILO", D("1"))]
        for p in ("polo",)
        for t in ("S", "M", "L", "XL")
    }
    return AlmacenMemoria(materiales, recetas, {"TEL-DRYFIT": D(dryfit), "INS-HILO": D("500")})


@pytest.fixture
def construir():
    """Devuelve una fábrica (grafo, servicios) configurable por prueba."""

    def _construir(interprete=None, evaluador=None, almacen=None):
        servicios = Servicios(
            pedidos=PedidosMemoria(),
            almacen=almacen or almacen_semilla(),
            notificador=NotificadorMemoria(),
            interprete=interprete or FakeInterprete(),
            evaluador=evaluador or FakeEvaluador(),
        )
        return construir_grafo(servicios, MemorySaver(), reintento_inicial_s=0.01), servicios

    return _construir


@pytest.fixture
def nuevo_pedido():
    def _pedido(cantidad: int = 10, talla: str = "M", prenda: str = "polo", sha: str = "a" * 64):
        return PedidoEntrada(
            pedido_id=f"P-{uuid.uuid4().hex[:8]}",
            cliente_id="C-001",
            correo_cliente="cli@x.pe",
            boceto_uri="/tmp/boceto.png",
            boceto_sha256=sha,
            lineas=[LineaPedido(prenda=prenda, talla=talla, color="azul", cantidad=cantidad)],
        )

    return _pedido
