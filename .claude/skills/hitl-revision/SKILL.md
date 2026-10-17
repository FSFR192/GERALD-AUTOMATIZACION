---
name: hitl-revision
description: Implementación de la revisión humana por excepción (administrador) y la aceptación del cliente con LangGraph interrupt(), checkpointer PostgreSQL, reanudación con Command(resume) y SLA 24 h / 48 h. Úsala al tocar el nodo de revisión, la cotización o los endpoints de aprobación.
---

# Human-in-the-loop (HITL)

Referencia: `docs/protocolos/P04-hitl.md`.

## Dos pausas humanas en todo el flujo
| Pausa | Quién | Cuándo | SLA | Al vencer |
|---|---|---|---|---|
| `revision_admin` | Administrador | veredicto de política = `revision` | 24 h | recordar y escalar |
| `aceptacion_cliente` | Cliente | siempre, tras cotizar | 48 h | recordatorio automático (1 vez); a las 96 h, cerrar como no contratado |

## Patrón

```python
from langgraph.types import interrupt


def revision_admin(state: GeraldState) -> dict:
    respuesta = interrupt(
        {
            "tipo": "revision_admin",
            "pedido_id": state["pedido"].pedido_id,
            "borrador": state["calculo"].model_dump(mode="json"),
            "motivo": state["veredicto"].motivo,
        }
    )
    return {"aprobacion_admin": AprobacionAdmin.model_validate(respuesta)}
```

Reanudar desde la API:

```python
from langgraph.types import Command

grafo.invoke(
    Command(resume={"aprobado": True, "comentario": ""}),
    config={"configurable": {"thread_id": pedido_id}},
)
```

## Reglas
- `thread_id` = `pedido_id` siempre.
- El checkpointer es `PostgresSaver`; nunca `MemorySaver` fuera de pruebas.
- La bandeja del administrador lista pedidos con `estado = 'en_revision'`; un clic aprueba o rechaza (rechazo exige comentario, que se convierte en observación al cliente).
- El SLA lo vigila `tareas.vigilar_sla()`; no uses timers dentro del grafo.
- Toda decisión humana se registra en `auditoria` y como etiqueta en `etiquetas_calibracion`.
