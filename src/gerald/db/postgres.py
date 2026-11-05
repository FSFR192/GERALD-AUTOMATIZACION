"""Implementaciones PostgreSQL de los puertos (producción). Consultas siempre parametrizadas."""

from contextlib import contextmanager
from decimal import Decimal
from typing import Any

from psycopg import OperationalError
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from gerald.config import Parametros
from gerald.errores import ErrorSistema, ErrorTransitorio
from gerald.schemas.pedido import PedidoEntrada
from gerald.schemas.resultados import CalculoMateriales, Material


@contextmanager
def _tx(pool: ConnectionPool, origen: str):
    """Abre una transacción y traduce errores de conexión/permiso a la jerarquía de P05."""
    try:
        with pool.connection(timeout=5) as cx, cx.transaction():
            yield cx
    except OperationalError as exc:
        raise ErrorTransitorio(origen, "base de datos no disponible") from exc
    except PermissionError as exc:
        raise ErrorSistema(origen, "permiso denegado en base de datos") from exc


def cargar_parametros(pool: ConnectionPool) -> Parametros:
    """Parámetros de la política desde la tabla `parametros`; claves ausentes → valor por defecto."""
    with _tx(pool, "parametros") as cx:
        filas = cx.execute("SELECT clave, valor FROM parametros").fetchall()
    return Parametros.model_validate({c: v for c, v in filas if c in Parametros.model_fields})


class PedidosPG:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    def existe_clave(self, clave: str) -> str | None:
        with _tx(self.pool, "pedidos") as cx:
            fila = cx.execute(
                "SELECT pedido_id FROM pedidos WHERE clave_idempotencia = %s", (clave,)
            ).fetchone()
        return fila[0] if fila else None

    def de_cliente(self, cliente_id: str) -> list[str]:
        with _tx(self.pool, "pedidos") as cx:
            filas = cx.execute(
                "SELECT pedido_id FROM pedidos WHERE cliente_id = %s ORDER BY creado_en DESC LIMIT 100",
                (cliente_id,),
            ).fetchall()
        return [f[0] for f in filas]

    def registrar(self, pedido: PedidoEntrada, clave: str) -> None:
        try:
            with _tx(self.pool, "registro") as cx:
                cx.execute(
                    "INSERT INTO pedidos (pedido_id, cliente_id, clave_idempotencia, carga) "
                    "VALUES (%s, %s, %s, %s) ON CONFLICT (clave_idempotencia) DO NOTHING",
                    (
                        pedido.pedido_id,
                        pedido.cliente_id,
                        clave,
                        Jsonb(pedido.model_dump(mode="json")),
                    ),
                )
        except ErrorTransitorio:
            raise
        except Exception as exc:
            raise ErrorSistema("registro", "no se pudo registrar el pedido") from exc

    def estado_de(self, pedido_id: str) -> str | None:
        with _tx(self.pool, "pedidos") as cx:
            fila = cx.execute("SELECT estado FROM pedidos WHERE pedido_id = %s", (pedido_id,)).fetchone()
        return fila[0] if fila else None

    def actualizar_estado(self, pedido_id: str, estado: str) -> None:
        with _tx(self.pool, "pedidos") as cx:
            cx.execute(
                "UPDATE pedidos SET estado = %s, actualizado_en = now() WHERE pedido_id = %s",
                (estado, pedido_id),
            )

    def registrar_contrato(self, pedido_id: str, calculo: CalculoMateriales) -> None:
        with _tx(self.pool, "contrato") as cx:
            cx.execute(
                "INSERT INTO contratos (pedido_id, calculo, costo_total_pen) VALUES (%s, %s, %s) "
                "ON CONFLICT (pedido_id) DO NOTHING",
                (pedido_id, Jsonb(calculo.model_dump(mode="json")), calculo.costo_total_pen),
            )

    def encolar_pendiente(self, pedido_id: str, carga: dict[str, Any], motivo: str) -> None:
        with _tx(self.pool, "cola") as cx:
            cx.execute(
                "INSERT INTO cola_pendientes (pedido_id, carga, motivo) VALUES (%s, %s, %s) "
                "ON CONFLICT (pedido_id) DO UPDATE SET carga = EXCLUDED.carga, motivo = EXCLUDED.motivo",
                (pedido_id, Jsonb(carga), motivo),
            )

    def tomar_pendientes(self, max_reprocesos: int) -> list[tuple[str, int]]:
        with _tx(self.pool, "cola") as cx:
            filas = cx.execute(
                "UPDATE cola_pendientes SET reprocesos = reprocesos + 1 "
                "WHERE reprocesos < %s RETURNING pedido_id, reprocesos",
                (max_reprocesos,),
            ).fetchall()
        return [(f[0], f[1]) for f in filas]

    def quitar_pendiente(self, pedido_id: str) -> None:
        with _tx(self.pool, "cola") as cx:
            cx.execute("DELETE FROM cola_pendientes WHERE pedido_id = %s", (pedido_id,))

    def registrar_etiqueta(self, pedido_id: str, etiqueta: dict[str, Any]) -> None:
        with _tx(self.pool, "calibracion") as cx:
            cx.execute(
                "INSERT INTO etiquetas_calibracion (pedido_id, etiqueta) VALUES (%s, %s)",
                (pedido_id, Jsonb(etiqueta)),
            )

    def etiquetas(self, dias: int) -> list[dict[str, Any]]:
        with _tx(self.pool, "calibracion") as cx:
            filas = cx.execute(
                "SELECT pedido_id, etiqueta FROM etiquetas_calibracion "
                "WHERE creado_en >= now() - make_interval(days => %s) ORDER BY id",
                (dias,),
            ).fetchall()
        return [{"pedido_id": f[0], **f[1]} for f in filas]

    def auditar(self, actor: str, accion: str, pedido_id: str, detalle: dict[str, Any]) -> None:
        with _tx(self.pool, "auditoria") as cx:
            cx.execute(
                "INSERT INTO auditoria (actor, accion, pedido_id, detalle) VALUES (%s,%s,%s,%s)",
                (actor, accion, pedido_id, Jsonb(detalle)),
            )

    def vencidos(self, estado: str, horas: int) -> list[str]:
        with _tx(self.pool, "sla") as cx:
            filas = cx.execute(
                "SELECT pedido_id FROM pedidos WHERE estado = %s "
                "AND actualizado_en <= now() - make_interval(hours => %s)",
                (estado, horas),
            ).fetchall()
        return [f[0] for f in filas]


class AlmacenPG:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    def materiales(self, ids: list[str]) -> dict[str, Material]:
        with _tx(self.pool, "catalogo") as cx:
            filas = cx.execute(
                "SELECT material_id, nombre, tipo, unidad, precio_unitario_pen, activo "
                "FROM materiales WHERE material_id = ANY(%s)",
                (ids,),
            ).fetchall()
        return {
            f[0]: Material(
                material_id=f[0],
                nombre=f[1],
                tipo=f[2],
                unidad=f[3],
                precio_unitario_pen=f[4],
                activo=f[5],
            )
            for f in filas
        }

    def receta(self, prenda: str, talla: str) -> list[tuple[str, Decimal]]:
        with _tx(self.pool, "catalogo") as cx:
            return [
                (f[0], f[1])
                for f in cx.execute(
                    "SELECT material_id, cantidad FROM recetas WHERE prenda = %s AND talla = %s",
                    (prenda, talla),
                ).fetchall()
            ]

    def prendas(self) -> dict[str, list[str]]:
        with _tx(self.pool, "catalogo") as cx:
            filas = cx.execute(
                "SELECT prenda, array_agg(talla ORDER BY array_position("
                "ARRAY['XS','S','M','L','XL','XXL'], talla)) FROM "
                "(SELECT DISTINCT prenda, talla FROM recetas) r GROUP BY prenda ORDER BY prenda"
            ).fetchall()
        return {f[0]: list(f[1]) for f in filas}

    def requerimientos_pendientes(self) -> list[dict[str, Any]]:
        with _tx(self.pool, "abastecimiento") as cx:
            filas = cx.execute(
                "SELECT pedido_id, material_id, faltante FROM requerimientos_abastecimiento "
                "WHERE estado = 'pendiente' ORDER BY id"
            ).fetchall()
        return [{"pedido_id": f[0], "material_id": f[1], "faltante": f[2]} for f in filas]

    def stock(self, ids: list[str]) -> dict[str, Decimal]:
        with _tx(self.pool, "inventario") as cx:
            filas = cx.execute(
                "SELECT material_id, disponible FROM inventario WHERE material_id = ANY(%s)", (ids,)
            ).fetchall()
        return {f[0]: f[1] for f in filas}

    def reservar(self, pedido_id: str, requeridos: dict[str, Decimal]) -> dict[str, Decimal]:
        """Transacción única con bloqueo de filas (SELECT ... FOR UPDATE). Idempotente por pedido."""
        try:
            with _tx(self.pool, "reserva") as cx:
                if cx.execute("SELECT 1 FROM reservas WHERE pedido_id = %s LIMIT 1", (pedido_id,)).fetchone():
                    return {}
                filas = cx.execute(
                    "SELECT material_id, disponible FROM inventario WHERE material_id = ANY(%s) "
                    "ORDER BY material_id FOR UPDATE",
                    (list(requeridos),),
                ).fetchall()
                disponible = {f[0]: f[1] for f in filas}
                faltantes = {
                    m: c - disponible.get(m, Decimal(0))
                    for m, c in requeridos.items()
                    if disponible.get(m, Decimal(0)) < c
                }
                if faltantes:
                    return faltantes
                for m, c in requeridos.items():
                    cx.execute(
                        "UPDATE inventario SET disponible = disponible - %s, "
                        "reservado = reservado + %s WHERE material_id = %s",
                        (c, c, m),
                    )
                    cx.execute(
                        "INSERT INTO reservas (pedido_id, material_id, cantidad) VALUES (%s, %s, %s)",
                        (pedido_id, m, c),
                    )
                return {}
        except ErrorTransitorio:
            raise
        except Exception as exc:
            raise ErrorSistema("reserva", "falló la reserva de materiales") from exc

    def crear_requerimiento(self, pedido_id: str, faltantes: dict[str, Decimal]) -> None:
        with _tx(self.pool, "abastecimiento") as cx:
            for m, f in faltantes.items():
                cx.execute(
                    "INSERT INTO requerimientos_abastecimiento (pedido_id, material_id, faltante) "
                    "VALUES (%s, %s, %s)",
                    (pedido_id, m, f),
                )

    def ingresar(self, material_id: str, cantidad: Decimal) -> list[str]:
        """Registra ingreso de material; devuelve los pedidos que esperaban ese material."""
        with _tx(self.pool, "abastecimiento") as cx:
            cx.execute(
                "UPDATE inventario SET disponible = disponible + %s WHERE material_id = %s",
                (cantidad, material_id),
            )
            filas = cx.execute(
                "UPDATE requerimientos_abastecimiento SET estado = 'atendido' "
                "WHERE material_id = %s AND estado = 'pendiente' RETURNING pedido_id",
                (material_id,),
            ).fetchall()
        return sorted({f[0] for f in filas})
