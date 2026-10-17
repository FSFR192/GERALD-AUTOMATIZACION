---
description: Verificar que todas las rutas del BPMN TO-BE estén implementadas y probadas
---

Usa el subagente `qa-flujos`:

1. Lee `docs/MAPEO-BPMN.md` y la matriz de la skill `pruebas-flujo`.
2. Ejecuta `uv run pytest -q`.
3. Entrega la tabla de cobertura: ruta BPMN → nodo/función → prueba → resultado.
4. Lista rutas sin implementación o sin prueba y propón cómo cerrarlas.
