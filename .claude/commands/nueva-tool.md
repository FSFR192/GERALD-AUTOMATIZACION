---
description: Crear una herramienta (@tool) para un agente específico
argument-hint: <nombre_tool> <agente_dueño> <qué hace>
---

Crea la tool `$ARGUMENTS` siguiendo la skill `nueva-herramienta`:

1. Entrada Pydantic, timeout, errores clasificados (P05), idempotencia si escribe.
2. Asígnala solo al agente dueño y regístrala en la tabla de `docs/protocolos/P06-herramientas.md`.
3. Agrega pruebas: caso feliz, timeout → `ErrorTransitorio`, entrada inválida.
4. Ejecuta `uv run ruff check . && uv run pytest -q`.
