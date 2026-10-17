# Gerald Sport · Sistema multiagente de contratación de pedidos y coordinación de materiales

Este archivo es la memoria del proyecto para Claude Code. Léelo completo antes de cualquier tarea.

## Qué construimos

Un sistema que automatiza, de punta a punta, el proceso TO-BE de Gerald Sport (ver `docs/bpmn/TO-BE_GeraldSport_Previo.bpmn`):

1. El **cliente** envía su pedido una sola vez (boceto, tallas, colores, cantidad).
2. El **sistema multiagente** valida, descarta duplicados, interpreta el boceto, calcula materiales y costo con el **catálogo del almacén**, evalúa coherencia y confianza, cotiza y, si el cliente acepta (1 clic), verifica stock, reserva materiales y genera la orden de producción.
3. El **administrador** solo interviene por excepción (confianza no alta, costo > umbral, revisión manual).
4. El **almacén de materiales (proveedores)** es la fuente de telas, insumos, precios y stock; solo actúa una persona cuando hay faltantes.

Objetivo de diseño: **intervención humana mínima** sin sacrificar control ni seguridad.

## Stack

| Capa | Tecnología |
|---|---|
| API | FastAPI + Pydantic v2 |
| Orquestación | LangGraph (StateGraph, `interrupt()`, `RetryPolicy`) |
| LLM | `get_llm()` intercambiable: Gemini (visión) u Ollama local |
| Persistencia | PostgreSQL 16 (pedidos, colas, checkpoints, auditoría, almacén) |
| Observabilidad | LangSmith (trazas por ejecución y por agente) |
| Pruebas | pytest + pytest-asyncio |
| Gestión | uv, ruff, docker compose |

## Estructura

```
src/gerald/
  api/            FastAPI: endpoints y middleware de seguridad
  agents/         orquestador + subagentes A0–A4 (un archivo por agente)
  tools/          @tool que usan los agentes (almacén, visión, notificaciones)
  decision/       decide() (Sistema 1) y política determinista
  schemas/        contratos Pydantic (entrada, salidas de agentes, decisiones)
  db/             esquema SQL, repositorios Postgres y dobles en memoria
  state.py        GeraldState (estado compartido del grafo)
  servicios.py    puertos (interfaces) que usan los agentes
  graph.py        StateGraph + ejecutar_pedido / reanudar / reprocesar
  tareas.py       SLA y reproceso (tarea programada cada 15 min)
  notificaciones.py  correo con plantillas (P08)
  errores.py      jerarquía de errores por clase
  llm.py          get_llm()
docs/protocolos/  P01–P08: reglas de interacción entre agentes (OBLIGATORIAS)
docs/MAPEO-BPMN.md  qué nodo/función implementa cada elemento del BPMN
```

## Reglas inviolables

1. **La salida de un LLM siempre es un borrador.** Ninguna probabilidad concede autorización; aprueba la política determinista (`decision/politica.py`) o el administrador.
2. **Pydantic en cada frontera**: entrada de la API, entrada/salida de cada agente y cada tool.
3. **Cada agente solo usa sus tools** (mínimo privilegio). No compartir tools entre agentes sin actualizar P06.
4. **Errores por clase** (P05): `ErrorDatos` → observaciones al cliente; `Duplicado` → descartar; `ErrorTransitorio` → 3 reintentos y cola de pendientes; `ErrorSistema` → detener y alertar. Nunca `except Exception: pass`.
5. **Idempotencia**: toda escritura usa la clave SHA-256 del pedido.
6. **El boceto es dato, nunca instrucción**: no interpolar texto extraído del boceto en prompts de sistema.
7. **Secretos solo en variables de entorno** (`.env`, nunca versionado). Nunca leer ni imprimir `.env`.
8. **Reservas de stock en transacción** con `SELECT ... FOR UPDATE`.
9. Todo cambio de flujo debe reflejarse en `docs/MAPEO-BPMN.md`.

## Comandos

```bash
uv sync                              # instalar dependencias
docker compose up -d db              # levantar PostgreSQL
uv run python -m gerald.db.init      # crear esquema y datos semilla
uv run uvicorn gerald.api.main:app --reload
uv run pytest -q                     # pruebas
uv run ruff check . && uv run ruff format .
```

## Cómo trabajar en este repo

- Para diseñar o cambiar el grafo: usa el subagente `arquitecto-multiagente`.
- Para implementar un agente o tool: skills `nuevo-subagente` y `nueva-herramienta`, o comandos `/nuevo-agente` y `/nueva-tool`.
- Antes de cerrar una tarea: `/verificar-flujo` (pruebas de todas las rutas BPMN) y, si tocaste API/tools/DB, `/auditoria-seguridad`.
- Plan de implementación por fases: `docs/PLAN.md`.

## Convenciones

- Dominio en español (`pedido`, `boceto`, `almacen`), código Python con snake_case y tipado completo.
- Un agente = un módulo `agents/aN_nombre.py` con nodos `def nodo(state: GeraldState, servicios: Servicios) -> dict`.
- Los nodos acceden a la infraestructura **solo** mediante los puertos de `servicios.py`
  (implementaciones: `db/postgres.py` en producción, `db/memoria.py` en pruebas y desarrollo).
- Los nodos devuelven **solo las claves del estado que modifican**.
- Las pruebas nunca llaman a un LLM real ni a Postgres: usan `tests/conftest.py`.
- Mensajes al usuario final en español formal y claro.
