"""Puertos (interfaces) hacia la infraestructura. Los agentes dependen de estos, no de Postgres ni del LLM.

Implementaciones:
- Producción: `gerald.db.postgres`, `gerald.notificaciones`, `gerald.agents.a2_boceto.InterpreteVision`,
  `gerald.decision.decide.EvaluadorLLM`.
- Pruebas / desarrollo: `gerald.db.memoria` y dobles en `tests/conftest.py`.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from gerald.config import Parametros
from gerald.schemas.pedido import PedidoEntrada
from gerald.schemas.resultados import (
    CalculoMateriales,
    Decision,
    InterpretacionBoceto,
    Material,
)


class RepoPedidos(Protocol):
    def existe_clave(self, clave: str) -> str | None: ...
    def registrar(self, pedido: PedidoEntrada, clave: str) -> None: ...
    def actualizar_estado(self, pedido_id: str, estado: str) -> None: ...
    def registrar_contrato(self, pedido_id: str, calculo: CalculoMateriales) -> None: ...
    def encolar_pendiente(self, pedido_id: str, carga: dict[str, Any], motivo: str) -> None:
        """Una fila por pedido (upsert): conserva el contador de reprocesos."""
        ...

    def tomar_pendientes(self, max_reprocesos: int) -> list[tuple[str, int]]:
        """Pedidos a reprocesar con su número de intento (incrementa el contador)."""
        ...

    def quitar_pendiente(self, pedido_id: str) -> None: ...

    def vencidos(self, estado: str, horas: int) -> list[str]: ...
    def registrar_etiqueta(self, pedido_id: str, etiqueta: dict[str, Any]) -> None: ...
    def etiquetas(self, dias: int) -> list[dict[str, Any]]:
        """Etiquetas de calibración de los últimos `dias` días (bucle de calibración, P03)."""
        ...

    def auditar(self, actor: str, accion: str, pedido_id: str, detalle: dict[str, Any]) -> None: ...


class RepoAlmacen(Protocol):
    def materiales(self, ids: list[str]) -> dict[str, Material]: ...
    def receta(self, prenda: str, talla: str) -> list[tuple[str, Decimal]]: ...
    def stock(self, ids: list[str]) -> dict[str, Decimal]: ...
    def reservar(self, pedido_id: str, requeridos: dict[str, Decimal]) -> dict[str, Decimal]:
        """Reserva en una transacción. Devuelve faltantes ({} si se reservó todo)."""
        ...

    def crear_requerimiento(self, pedido_id: str, faltantes: dict[str, Decimal]) -> None: ...
    def ingresar(self, material_id: str, cantidad: Decimal) -> list[str]:
        """Registra el ingreso de material; devuelve los pedidos cuyo requerimiento quedó atendido."""
        ...


class Notificador(Protocol):
    def enviar(self, evento: str, destinatario: str, pedido_id: str, datos: dict[str, Any]) -> None: ...


class InterpreteBoceto(Protocol):
    def __call__(self, pedido: PedidoEntrada) -> InterpretacionBoceto: ...


class Ocr(Protocol):
    def __call__(self, pedido: PedidoEntrada) -> list[str]:
        """Textos visibles en el boceto. Son datos del cliente, nunca instrucciones."""
        ...


class Evaluador(Protocol):
    def __call__(
        self, pedido: PedidoEntrada, boceto: InterpretacionBoceto, calculo: CalculoMateriales
    ) -> Decision: ...


@dataclass
class Servicios:
    pedidos: RepoPedidos
    almacen: RepoAlmacen
    notificador: Notificador
    interprete: InterpreteBoceto
    evaluador: Evaluador
    parametros: Parametros = field(default_factory=Parametros)
    ocr: Ocr | None = None
    correo_admin: str = "admin@geraldsport.pe"
    correo_almacen: str = "almacen@geraldsport.pe"
