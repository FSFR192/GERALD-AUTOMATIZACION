"""Crea el esquema, las tablas de checkpoints y datos semilla. Uso: uv run python -m gerald.db.init"""

from pathlib import Path

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

from gerald.config import settings
from gerald.db import semilla


def sembrar(cx: psycopg.Connection) -> None:
    """Inserta la semilla de `gerald.db.semilla`. Idempotente (ON CONFLICT DO NOTHING)."""
    with cx.cursor() as cur:
        cur.executemany(
            "INSERT INTO materiales VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            [
                (m.material_id, m.nombre, m.tipo, m.unidad, m.precio_unitario_pen, m.activo)
                for m in semilla.MATERIALES
            ],
        )
        cur.executemany(
            "INSERT INTO recetas VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            [
                (prenda, talla, material_id, cantidad)
                for (prenda, talla), receta in semilla.RECETAS.items()
                for material_id, cantidad in receta
            ],
        )
        cur.executemany(
            "INSERT INTO inventario VALUES (%s, %s, 0) ON CONFLICT DO NOTHING",
            list(semilla.INVENTARIO.items()),
        )
        cur.executemany(
            "INSERT INTO parametros (clave, valor) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            list(semilla.PARAMETROS.items()),
        )


def crear_esquema(url: str) -> None:
    esquema = (Path(__file__).parent / "esquema.sql").read_text(encoding="utf-8")
    with psycopg.connect(url, autocommit=True) as cx:
        cx.execute(esquema)
        sembrar(cx)
    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()


def main() -> None:
    crear_esquema(settings().database_url.get_secret_value())
    print("Esquema, checkpoints y semilla listos.")


if __name__ == "__main__":
    main()
