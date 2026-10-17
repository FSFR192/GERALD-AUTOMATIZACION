# P08 · Protocolo de notificaciones

Todas las notificaciones las emite **A4** mediante `enviar_correo` y plantillas en `src/gerald/plantillas/`.

| Evento | Destinatario | Plantilla | Contenido mínimo |
|---|---|---|---|
| Pedido recibido | Cliente, admin | `recepcion` | número de pedido, resumen |
| Observaciones | Cliente | `observaciones` | lista accionable + enlace para corregir |
| Duplicado | Cliente | `duplicado` | número del pedido existente |
| Revisión requerida | Admin | `revision` | motivo + enlace 1 clic (aprobar/rechazar) |
| Cotización y contrato | Cliente | `cotizacion` | detalle, costo, enlace 1 clic para aceptar |
| Recordatorio | Cliente / admin | `recordatorio` | lo pendiente y vencimiento |
| Requerimiento de abastecimiento | Almacén | `abastecimiento` | materiales, faltantes, fecha requerida |
| Pedido confirmado | Cliente, admin | `confirmado` | fecha estimada, lista de materiales |
| Alerta de sistema | Responsable | `alerta` | pedido, agente, error (sin datos sensibles) |

## Reglas
- Idempotentes: clave `(pedido_id, evento)`; no se reenvía dos veces el mismo aviso.
- Fallo de envío = `ErrorTransitorio` (reintento); no bloquea el flujo principal salvo la cotización.
- Español formal, breve, con un solo llamado a la acción.
