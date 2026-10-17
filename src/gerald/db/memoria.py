"""Implementaciones en memoria de los puertos, para pruebas y desarrollo local sin PostgreSQL."""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from gerald.schemas.pedido import PedidoEntrada
from gerald.schemas.resultados import CalculoMateriales, Material


class PedidosMemoria:
    def __init__(self) -> None:
        self.pedidos: dict[str, dict[str, Any]] = {}
        self.claves: dict[str, str] = {}
        self.contratos: dict[str, CalculoMateriales] = {}
        self.pendientes: list[dict[str, Any]] = []
        self.etiquetas_registradas: list[dict[str, Any]] = []
        self.auditoria: list[dict[str, Any]] = []

    def existe_clave(self, clave: str) -> str | None:
        return self.claves.get(clave)

    def registrar(self, pedido: PedidoEntrada, clave: str) -> None:
        self.claves[clave] = pedido.pedido_id
        self.pedidos[pedido.pedido_id] = {"estado": "recibido", "cambio": datetime.now(UTC)}

    def actualizar_estado(self, pedido_id: str, estado: str) -> None:
        self.pedidos.setdefault(pedido_id, {}).update(estado=estado, cambio=datetime.now(UTC))

    def registrar_contrato(self, pedido_id: str, calculo: CalculoMateriales) -> None:
        self.contratos[pedido_id] = calculo

    def encolar_pendiente(self, pedido_id: str, carga: dict[str, Any], motivo: str) -> None:
        for p in self.pendientes:
            if p["pedido_id"] == pedido_id:
                p.update(carga=carga, motivo=motivo)
                return
        self.pendientes.append({"pedido_id": pedido_id, "carga": carga, "motivo": motivo, "reprocesos": 0})

    def tomar_pendientes(self, max_reprocesos: int) -> list[tuple[str, int]]:
        tomados = []
        for p in self.pendientes:
            if p["reprocesos"] < max_reprocesos:
                p["reprocesos"] += 1
                tomados.append((p["pedido_id"], p["reprocesos"]))
        return tomados

    def quitar_pendiente(self, pedido_id: str) -> None:
        self.pendientes = [p for p in self.pendientes if p["pedido_id"] != pedido_id]

    def registrar_etiqueta(self, pedido_id: str, etiqueta: dict[str, Any]) -> None:
        self.etiquetas_registradas.append({"pedido_id": pedido_id, **etiqueta})

    def etiquetas(self, dias: int) -> list[dict[str, Any]]:
        return list(self.etiquetas_registradas)

    def auditar(self, actor: str, accion: str, pedido_id: str, detalle: dict[str, Any]) -> None:
        self.auditoria.append({"actor": actor, "accion": accion, "pedido_id": pedido_id})

    def vencidos(self, estado: str, horas: int) -> list[str]:
        limite = datetime.now(UTC).timestamp() - horas * 3600
        return [
            pid
            for pid, p in self.pedidos.items()
            if p.get("estado") == estado and p["cambio"].timestamp() <= limite
        ]


class AlmacenMemoria:
    def __init__(
        self,
        materiales: list[Material],
        recetas: dict[tuple[str, str], list[tuple[str, Decimal]]],
        inventario: dict[str, Decimal],
    ) -> None:
        self._materiales = {m.material_id: m for m in materiales}
        self._recetas = recetas
        self.disponible = dict(inventario)
        self.reservado: dict[str, Decimal] = defaultdict(Decimal)
        self.reservas: dict[str, dict[str, Decimal]] = {}
        self.requerimientos: list[dict[str, Any]] = []

    def materiales(self, ids: list[str]) -> dict[str, Material]:
        return {i: self._materiales[i] for i in ids if i in self._materiales}

    def receta(self, prenda: str, talla: str) -> list[tuple[str, Decimal]]:
        return self._recetas.get((prenda, talla), [])

    def stock(self, ids: list[str]) -> dict[str, Decimal]:
        return {i: self.disponible.get(i, Decimal(0)) for i in ids}

    def reservar(self, pedido_id: str, requeridos: dict[str, Decimal]) -> dict[str, Decimal]:
        if pedido_id in self.reservas:  # idempotente
            return {}
        faltantes = {
            m: c - self.disponible.get(m, Decimal(0))
            for m, c in requeridos.items()
            if self.disponible.get(m, Decimal(0)) < c
        }
        if faltantes:
            return faltantes
        for m, c in requeridos.items():
            self.disponible[m] -= c
            self.reservado[m] += c
        self.reservas[pedido_id] = dict(requeridos)
        return {}

    def crear_requerimiento(self, pedido_id: str, faltantes: dict[str, Decimal]) -> None:
        self.requerimientos.append({"pedido_id": pedido_id, "faltantes": faltantes, "estado": "pendiente"})

    def ingresar(self, material_id: str, cantidad: Decimal) -> list[str]:
        self.disponible[material_id] = self.disponible.get(material_id, Decimal(0)) + cantidad
        atendidos = set()
        for req in self.requerimientos:
            if req["estado"] == "pendiente" and material_id in req["faltantes"]:
                req["estado"] = "atendido"
                atendidos.add(req["pedido_id"])
        return sorted(atendidos)


class NotificadorMemoria:
    def __init__(self) -> None:
        self.enviados: list[dict[str, Any]] = []

    def enviar(self, evento: str, destinatario: str, pedido_id: str, datos: dict[str, Any]) -> None:
        self.enviados.append({"evento": evento, "para": destinatario, "pedido_id": pedido_id, **datos})

    def eventos(self) -> list[str]:
        return [e["evento"] for e in self.enviados]
