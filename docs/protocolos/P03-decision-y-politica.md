# P03 · Protocolo de decisión y política

## Dos capas
1. **`decide()` — Sistema 1 (evalúa)**. Usa el LLM con salida estructurada `Decision`:
   `coherente`, `puntaje (0..1)`, `confianza`, `razones`. Verifica coherencia boceto ↔ prenda ↔ receta ↔ costo.
   Respaldo intercambiable: reglas fijas si el LLM falla (confianza = baja).
2. **`politica.evaluar()` — determinista (autoriza)**. Código puro, sin LLM, con parámetros de la tabla `parametros`.

## Tabla de decisión

| Coherente | Confianza (recalculada por puntaje) | Costo ≤ umbral | Veredicto | Ruta BPMN |
|---|---|---|---|---|
| No | — | — | `observar` | Enviar observaciones al cliente |
| Sí | alta | Sí | `aprobar` | Aprobación automática |
| Sí | alta | No | `revision` | Revisar y aprobar propuesta |
| Sí | media | — | `revision` | Revisar y aprobar propuesta |
| Sí | baja | — | `revision` (manual) | Revisar y aprobar propuesta |

Confianza a partir de `puntaje`: ≥ 0.85 alta; ≥ 0.60 media; < 0.60 baja.

## Parámetros (tabla `parametros`)
| Clave | Valor inicial |
|---|---|
| `umbral_costo_pen` | 300.00 |
| `merma_pct` | 8 |
| `puntaje_minimo_alta` | 0.85 |
| `puntaje_minimo_media` | 0.60 |
| `sla_revision_horas` | 24 |
| `sla_aceptacion_horas` | 48 |
| `max_reprocesos` | 3 |

## Bucle de calibración
Cada pedido registra en `etiquetas_calibracion`: puntaje, confianza, veredicto, resultado humano (aprobado/rechazado/aceptado/no aceptado). Un informe semanal compara confianza vs resultado y alerta deriva si la tasa de rechazo de pedidos con confianza alta supera 5 %.

Implementación: `gerald.calibracion.informe` (fallo = resultado `observado`/`no_contratado` o rechazo del admin;
muestra mínima 20 pedidos por tramo), `uv run python -m gerald.tareas calibracion` (semanal, alerta `calibracion`)
y `GET /calibracion` (administrador, auditor). Las sugerencias de umbral son borradores: nunca modifican
`parametros` automáticamente.
