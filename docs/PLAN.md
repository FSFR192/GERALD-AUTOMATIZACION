# Plan de implementación por fases

Cada fase termina con `/verificar-flujo` en verde y, si toca API/DB/tools, `/auditoria-seguridad` APTO.

## Fase 0 · Base (incluida en este repositorio)
- [x] Estado compartido, contratos Pydantic, jerarquía de errores, política determinista.
- [x] Agentes A0–A4 y orquestador con servicios inyectados.
- [x] Grafo con RetryPolicy, pausas HITL y captura de errores por clase.
- [x] Dobles en memoria y 31 pruebas que recorren todas las rutas del BPMN.
- [x] API con puerta de seguridad (JWT, roles, límite de tasa, tipo y tamaño de archivo).

## Fase 1 · Persistencia real
- [ ] `docker compose up -d db` + `uv run python -m gerald.db.init`.
- [x] Pruebas de integración de `db/postgres.py` (reserva concurrente con FOR UPDATE) — `tests/test_postgres.py`, `-m integracion`. **Pendiente ejecutarlas con Docker activo.**
- [x] Cargar `Parametros` desde la tabla `parametros` al iniciar (`cargar_parametros`).
- [x] Semilla única `db/semilla.py`: 7 materiales, 14 recetas, inventario y parámetros.
- [x] Modo demo sin Postgres (`GERALD_MODO=demo`).
- Subagente: `ingeniero-datos`.

## Fase 2 · LLM real
- [ ] Configurar `GERALD_GOOGLE_API_KEY` y probar `InterpreteVision` con 10 bocetos reales.
- [ ] Ajustar prompt de `EvaluadorLLM`; medir puntaje vs revisión humana.
- [ ] Alternativa local con Ollama (`llava`) para desarrollo sin costo.
- Skills: `politica-decision`, `contratos-pydantic`.

## Fase 3 · Operación
- [ ] Programar `uv run python -m gerald.tareas` cada 15 min (cron o scheduler del servidor).
- [ ] Notificaciones reales (mailpit en desarrollo, SMTP en producción) con enlaces firmados de 1 clic.
- [ ] Bandeja del administrador y pantalla de aceptación del cliente (frontend).
- [x] LangSmith con datos personales ocultos (`observabilidad.configurar_trazas`).

## Fase 4 · Endurecimiento
- [ ] ClamAV (`docker compose --profile seguridad up -d`).
- [ ] Rol `gerald_app` con mínimo privilegio y auditoría solo inserción.
- [ ] Exponer las tools de A3 por un servidor MCP propio (`mcp-almacen`), si se requiere.
- [x] Informe semanal de calibración (confianza vs resultado) y alerta de deriva.
- [x] Tools @tool de A1, A2 (visión + OCR), A3 y A4 con `tools_de()` (P06).

## Cómo pedirle trabajo a Claude Code en Antigravity
- "Implementa la fase 1 siguiendo docs/PLAN.md" → usará `ingeniero-datos` y `qa-flujos`.
- `/nuevo-agente a5_produccion "programar la producción según capacidad del taller"`
- `/nueva-tool leer_capacidad a5_produccion "consulta horas disponibles del taller"`
- `/verificar-flujo` y `/auditoria-seguridad` antes de cada entrega.
