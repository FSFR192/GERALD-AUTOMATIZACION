# Gerald Sport · Sistema multiagente

Automatiza la **contratación de pedidos** y la **coordinación de materiales con el almacén** de Gerald Sport, siguiendo el BPMN TO-BE (`docs/bpmn/`). El cliente solo envía su pedido y acepta con un clic; el administrador interviene solo por excepción.

## Arranque rápido (Antigravity + Claude Code)

1. Abre esta carpeta en Antigravity y abre el panel de Claude Code. Claude leerá `CLAUDE.md` automáticamente.
2. Instala dependencias y corre las pruebas:
   ```bash
   uv sync
   uv run pytest -q
   ```
3. Para probar la API sin Docker ni Postgres (modo demo, datos en memoria):
   ```bash
   GERALD_MODO=demo uv run uvicorn gerald.api.main:app --reload     # http://localhost:8000/docs
   uv run python -m gerald.demo cliente C-001                       # token JWT de cliente
   uv run python -m gerald.demo administrador ADM-1                 # token de administrador
   ```
   Sin `GERALD_GOOGLE_API_KEY` todos los pedidos van a revisión del administrador (nunca se aprueba sin LLM).
4. Para levantar con base de datos real:
   ```bash
   cp .env.example .env          # completa tus claves
   docker compose up -d db
   uv run python -m gerald.db.init
   uv run uvicorn gerald.api.main:app --reload
   GERALD_TEST_DATABASE_URL=postgresql://gerald:gerald@localhost:5432/gerald uv run pytest -m integracion
   ```
5. Tareas programadas: `uv run python -m gerald.tareas` (cada 15 min) y `uv run python -m gerald.tareas calibracion` (semanal).

## Qué hay en `.claude/`

| Tipo | Nombre | Para qué |
|---|---|---|
| Subagente | `arquitecto-multiagente` | Diseña cambios al grafo/estado (solo lectura) |
| Subagente | `desarrollador-agentes` | Implementa nodos, tools y contratos |
| Subagente | `ingeniero-datos` | Esquema PostgreSQL, reservas, colas |
| Subagente | `auditor-seguridad` | Audita contra P07 (solo reporta) |
| Subagente | `qa-flujos` | Prueba cada ruta del BPMN |
| Skill | `nuevo-subagente`, `nueva-herramienta` | Plantillas de agentes y tools |
| Skill | `contratos-pydantic`, `manejo-errores` | Contratos de datos y errores por clase |
| Skill | `hitl-revision`, `politica-decision` | Pausas humanas y autorización |
| Skill | `almacen-materiales`, `pruebas-flujo` | Almacén (proveedores) y pruebas |
| Comando | `/nuevo-agente`, `/nueva-tool` | Flujos guiados de creación |
| Comando | `/verificar-flujo`, `/auditoria-seguridad` | Verificación antes de entregar |

## Protocolos (`docs/protocolos/`)
P01 estado compartido · P02 delegación · P03 decisión y política · P04 HITL · P05 errores · P06 herramientas · P07 seguridad · P08 notificaciones.

## Agentes del sistema

| Agente | Responsabilidad |
|---|---|
| GERALD-ORCH | Decide y aplica la política; gestiona pausas humanas |
| A0 Ingesta | Valida el pedido |
| A1 Recepción | Clave SHA-256, duplicados, registro y acuse |
| A2 Boceto | Interpreta el boceto con visión |
| A3 Materiales | Catálogo, recetas, costo, stock, reserva y abastecimiento |
| A4 Registro | Contrato, cotización, orden de producción y notificaciones |
