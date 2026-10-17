# P04 · Protocolo de intervención humana (HITL)

Objetivo: **el mínimo de clics**. Solo existen tres puntos humanos y dos son por excepción.

| Punto | Actor | Frecuencia | Acción | Mecanismo |
|---|---|---|---|---|
| Aceptar cotización | Cliente | Siempre (1 clic) | Aceptar / no aceptar | `interrupt()` en `aceptacion_cliente` |
| Revisar propuesta | Administrador | Solo si veredicto = `revision` | Aprobar / rechazar con comentario | `interrupt()` en `revision_admin` |
| Abastecer faltante | Almacén | Solo si falta stock | Registrar ingreso de material | endpoint `/almacen/ingresos` reanuda el pedido |

Corregir el pedido no es una pausa del mismo hilo: el cliente reenvía y se crea un hilo nuevo (nuevo hash).

## Reglas técnicas
1. `thread_id = pedido_id`; checkpointer `PostgresSaver`.
2. La carga del `interrupt` es JSON serializable con: `tipo`, `pedido_id`, `borrador`, `motivo`.
3. La respuesta se valida con Pydantic (`AprobacionAdmin`, `AceptacionCliente`) antes de reanudar.
4. Endpoints de reanudación autenticados y autorizados por rol (cliente dueño / administrador / almacén).
5. Enlaces de 1 clic: token firmado de un solo uso con vencimiento.

## SLA (tarea programada `tareas.vigilar_sla`, cada 15 min)
| Pausa | Vence | Acción |
|---|---|---|
| Revisión admin | 24 h | Recordatorio + escalamiento (correo al responsable) |
| Aceptación cliente | 48 h | Recordatorio automático; a las 96 h → `no_contratado` |
| Abastecimiento | fecha estimada | Alerta al administrador |
