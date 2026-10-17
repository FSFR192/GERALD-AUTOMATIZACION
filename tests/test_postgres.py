"""Integración con PostgreSQL real (fase 1). Opcional: se omite si no hay GERALD_TEST_DATABASE_URL.

    docker compose up -d db
    GERALD_TEST_DATABASE_URL=postgresql://gerald:gerald@localhost:5432/gerald uv run pytest -m integracion

Usa una base desechable: borra y recrea el esquema público.
"""

import os
import threading
from decimal import Decimal

import pytest

URL = os.environ.get("GERALD_TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integracion,
    pytest.mark.skipif(not URL, reason="sin GERALD_TEST_DATABASE_URL"),
]


@pytest.fixture
def pool():
    import psycopg
    from psycopg_pool import ConnectionPool

    from gerald.db.init import crear_esquema

    with psycopg.connect(URL, autocommit=True) as cx:
        cx.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    crear_esquema(URL)
    p = ConnectionPool(URL, kwargs={"autocommit": True, "prepare_threshold": 0}, open=True)
    yield p
    p.close()


def test_parametros_desde_tabla(pool):
    from gerald.db.postgres import cargar_parametros

    p = cargar_parametros(pool)
    assert p.umbral_costo_pen == Decimal("300.00")
    assert p.max_reprocesos == 3


def test_reserva_concurrente_no_sobrevende(pool):
    """Dos pedidos compiten por 200 m de dry-fit pidiendo 150 m cada uno: solo uno reserva."""
    from gerald.db.postgres import AlmacenPG

    almacen = AlmacenPG(pool)
    resultados: dict[str, dict] = {}

    def reservar(pid: str) -> None:
        resultados[pid] = almacen.reservar(pid, {"TEL-DRYFIT": Decimal("150")})

    hilos = [threading.Thread(target=reservar, args=(f"P-{i}",)) for i in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    exitosos = [pid for pid, faltantes in resultados.items() if not faltantes]
    assert len(exitosos) == 1
    assert almacen.stock(["TEL-DRYFIT"])["TEL-DRYFIT"] == Decimal("50")
    assert almacen.reservar(exitosos[0], {"TEL-DRYFIT": Decimal("150")}) == {}  # idempotente


def test_ingreso_atiende_requerimiento(pool):
    from gerald.db.postgres import AlmacenPG

    almacen = AlmacenPG(pool)
    almacen.crear_requerimiento("P-1", {"TEL-MICRO": Decimal("20")})
    assert almacen.ingresar("TEL-MICRO", Decimal("30")) == ["P-1"]
    assert almacen.ingresar("TEL-MICRO", Decimal("1")) == []


def test_registro_idempotente_y_etiquetas(pool):
    from gerald.db.postgres import PedidosPG
    from gerald.schemas.pedido import LineaPedido, PedidoEntrada

    repo = PedidosPG(pool)
    pedido = PedidoEntrada(
        pedido_id="P-1",
        cliente_id="C-1",
        correo_cliente="c@x.pe",
        boceto_uri="b.png",
        boceto_sha256="a" * 64,
        lineas=[LineaPedido(prenda="polo", talla="M", color="azul", cantidad=1)],
    )
    repo.registrar(pedido, "k" * 64)
    repo.registrar(pedido, "k" * 64)  # mismo pedido: no duplica
    assert repo.existe_clave("k" * 64) == "P-1"
    repo.registrar_etiqueta("P-1", {"confianza": "alta", "resultado": "contratado"})
    assert repo.etiquetas(7) == [{"pedido_id": "P-1", "confianza": "alta", "resultado": "contratado"}]
