---
name: nueva-herramienta
description: Plantilla para crear una @tool de LangChain en Gerald Sport (consultas al almacén, visión, notificaciones, registro) con entrada Pydantic, fábrica por agente, clasificación de errores y mínimo privilegio. Úsala al crear o modificar archivos en src/gerald/tools/ o métodos de los puertos que esas tools usan.
---

# Crear una herramienta (@tool)

## Dos niveles
1. **Puerto** (`servicios.py`) + implementación (`db/postgres.py`, `db/memoria.py`, …): aquí van las
   consultas, los timeouts y la traducción de errores. Los nodos usan el puerto directamente.
2. **@tool** (`tools/<agente>.py`): envoltura para que un LLM la invoque (modo ReAct) o para exponerla
   por MCP. Se crea con una **fábrica por agente**, así cada agente recibe solo sus tools.

## Reglas
1. Entrada definida con un modelo Pydantic (`args_schema`).
2. Timeout explícito en toda llamada externa (DB 5 s, LLM 30 s, correo 10 s).
3. La implementación del puerto traduce excepciones a `gerald.errores`:
   - Timeout, 429, 503, conexión caída → `ErrorTransitorio`
   - Credencial revocada, cuota agotada, error al escribir datos críticos → `ErrorSistema`
   - Datos inválidos del cliente → `ErrorDatos`
4. Escrituras idempotentes (clave de idempotencia o `ON CONFLICT DO NOTHING`).
5. Registrar la tool en la tabla de P06 con su **agente dueño**.
6. Docstring claro en español: el LLM lo lee para decidir cuándo usarla.

## Plantilla del puerto (Postgres)

```python
def stock(self, ids: list[str]) -> dict[str, Decimal]:
    with _tx(self.pool, "inventario") as cx:  # _tx traduce errores a P05
        filas = cx.execute(
            "SELECT material_id, disponible FROM inventario WHERE material_id = ANY(%s)", (ids,)
        ).fetchall()
    return {f[0]: f[1] for f in filas}
```

## Plantilla de la @tool (fábrica por agente)

```python
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from gerald.servicios import RepoAlmacen


class IdsMateriales(BaseModel):
    material_ids: list[str] = Field(..., min_length=1, max_length=50)


def crear_tools_almacen(almacen: RepoAlmacen) -> list[BaseTool]:
    @tool("consultar_stock", args_schema=IdsMateriales)
    def consultar_stock(material_ids: list[str]) -> dict[str, str]:
        """Devuelve el stock disponible por material en el almacén."""
        return {m: str(c) for m, c in almacen.stock(material_ids).items()}

    return [consultar_stock]
```

Ejemplo real: `src/gerald/tools/almacen.py` (tools de A3).

## Pruebas mínimas
- Caso feliz con el almacén semilla de `tests/conftest.py`.
- Falla simulada → excepción de la clase correcta.
- Entrada inválida → `ValidationError` antes de tocar la infraestructura.
