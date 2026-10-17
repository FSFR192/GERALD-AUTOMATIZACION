---
description: Crear un nuevo subagente del sistema (plan del arquitecto → implementación → pruebas)
argument-hint: <nombre> <responsabilidad>
---

Crea el subagente `$ARGUMENTS` del sistema Gerald Sport.

1. Usa el subagente `arquitecto-multiagente` para producir el plan (estado, nodos, tools, rutas de error, pruebas).
2. Muéstrame el plan y espera mi confirmación solo si cambia `GeraldState` de forma incompatible; si no, continúa.
3. Usa el subagente `desarrollador-agentes` con la skill `nuevo-subagente` para implementarlo.
4. Usa el subagente `qa-flujos` para agregar y correr las pruebas de sus rutas.
5. Actualiza `docs/MAPEO-BPMN.md`.
6. Resume: archivos creados, rutas cubiertas, pendientes.
