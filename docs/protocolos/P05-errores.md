# P05 · Protocolo de manejo de errores

Corresponde a los eventos de error del BPMN TO-BE.

## Jerarquía (`src/gerald/errores.py`)
```
ErrorGerald
├── ErrorDatos          → observaciones al cliente (no se reintenta)
├── Duplicado           → pedido descartado (no es falla)
├── ErrorTransitorio    → reintento automático
└── ErrorSistema        → detener y alertar
```

## Tratamiento

| Clase | Ejemplos | Reintento | Destino | Estado final |
|---|---|---|---|---|
| Datos | campo faltante, talla inexistente, archivo ilegible, salida LLM inválida | No | Observaciones al cliente / respuesta 400 | `observado` / `rechazado` |
| Duplicado | misma clave SHA-256 | No | Respuesta 200 sin nuevo registro | `duplicado` |
| Transitorio | timeout, 429, 503, catálogo o inventario no disponible | 3 intentos: 2 s, 4 s, 8 s | Agotados → `cola_pendientes` con carga completa | `pendiente_reproceso` |
| Sistema | cuota agotada, credencial revocada, esquema roto, error al registrar o reservar | No | Alerta al responsable | `detenido` |

## Puntos del BPMN con evento de error
| Tarea | Evento | Clase |
|---|---|---|
| Registrar pedido y confirmar recepción | Error de sistema (registro) | Sistema |
| Interpretar el boceto | Reintentos agotados (3) | Transitorio |
| Calcular materiales y costo | Catálogo no disponible | Transitorio |
| Verificar disponibilidad | Inventario no disponible | Transitorio |
| Reservar materiales | Error de sistema (reserva) | Sistema |

## Reproceso
`tareas.reprocesar_pendientes()` cada 15 min toma `cola_pendientes`, reanuda desde el último checkpoint y, tras 3 reprocesos fallidos, escala a sistema (alerta).

## Prohibiciones
No silenciar excepciones; no reintentar errores de datos o de sistema; no perder la carga del pedido; no exponer trazas internas al cliente.
