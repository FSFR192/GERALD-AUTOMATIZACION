---
name: manejo-errores
description: Cómo implementar el manejo de errores por clase de Gerald Sport (datos, duplicados, transitorios, sistema) con RetryPolicy, cola de pendientes, alertas y estado detenido, tal como lo define el BPMN TO-BE. Úsala al escribir nodos, tools o rutas de error.
---

# Manejo de errores por clase

Referencia normativa: `docs/protocolos/P05-errores.md`.

| Clase | Excepción | Qué pasa | Fin BPMN |
|---|---|---|---|
| Datos | `ErrorDatos` | Se generan observaciones y se notifica al cliente | Corregir pedido / Solicitud rechazada |
| Duplicado | `Duplicado` | Se informa que el pedido ya existe | Duplicado descartado |
| Transitorio | `ErrorTransitorio` | `RetryPolicy` 3 intentos (2 s, 4 s, 8 s); agotados → `cola_pendientes` con carga completa | Pendiente de reproceso |
| Sistema | `ErrorSistema` | Se detiene el grafo, se alerta al responsable, estado `detenido` | Flujo detenido |

## Implementación
1. **En tools**: traduce excepciones técnicas a estas clases (skill `nueva-herramienta`).
2. **En el grafo**: cada nodo lleva `retry_policy=REINTENTOS` (solo reintenta `ErrorTransitorio`).
3. **Captura final**: `graph._ejecutar()` (usado por `ejecutar_pedido`, `reanudar` y `reprocesar`)
   envuelve `grafo.invoke`:
   - `ErrorTransitorio` (reintentos agotados) → `pedidos.encolar_pendiente(...)` con el estado completo
     del checkpoint y estado `pendiente_reproceso`.
   - `ErrorSistema` → notificación `alerta` al responsable y estado `detenido`.
4. **Reproceso**: `tareas.reprocesar_pendientes()` (cada 15 min) reanuda desde el último checkpoint con
   el mismo `thread_id`. Si se recupera, sale de la cola; si falla en el intento `max_reprocesos`, alerta
   y queda `detenido`. La cola tiene **una fila por pedido**.
5. **Pruebas de referencia**: `tests/test_errores.py`.

## Prohibido
- `except Exception: pass` o capturar sin re-lanzar/clasificar.
- Reintentar `ErrorDatos` o `ErrorSistema`.
- Perder la carga del pedido: toda cola guarda el JSON completo.
