# P01 · Protocolo de estado compartido

Todos los agentes se comunican **solo a través de `GeraldState`** (`src/gerald/state.py`). No hay llamadas directas entre agentes.

## Regla de propiedad: una clave, un escritor

| Clave | Tipo | Escribe | Leen |
|---|---|---|---|
| `pedido` | `PedidoEntrada` | API (entrada) | todos |
| `clave_idempotencia` | `str` (SHA-256) | A1 | A4, orquestador |
| `es_duplicado` | `bool` | A1 | orquestador |
| `boceto` | `InterpretacionBoceto` | A2 | A3, decide |
| `calculo` | `CalculoMateriales` | A3 | decide, orquestador, A4 |
| `decision` | `Decision` | orquestador (decide) | orquestador |
| `veredicto` | `VeredictoPolitica` | orquestador (política) | orquestador, revisión admin |
| `aprobacion_admin` | `AprobacionAdmin \| None` | revisión admin (HITL) | orquestador |
| `aceptacion_cliente` | `AceptacionCliente \| None` | aceptación cliente (HITL) | orquestador |
| `reserva` | `Reserva` | A3 | A4 |
| `observaciones` | `list[str]` (acumulativa) | A0, A3, decide, admin | A4 |
| `estado` | `EstadoPedido` | orquestador | API, tareas |

## Reglas
1. Un nodo devuelve un `dict` **solo con sus claves**. LangGraph fusiona.
2. `observaciones` usa reductor de suma (`Annotated[list[str], operator.add]`); es la única clave con varios escritores.
3. El estado se persiste en cada paso mediante `PostgresSaver` con `thread_id = pedido_id`.
4. Nada de datos binarios en el estado: el boceto se guarda en almacenamiento de objetos y el estado lleva su `uri` y hash.
5. Agregar una clave exige actualizar esta tabla.

## Estados del pedido (`EstadoPedido`)
`recibido → interpretado → calculado → en_revision → cotizado → contratado → reservado → en_produccion`
Estados terminales alternos: `observado`, `duplicado`, `rechazado`, `no_contratado`, `pendiente_reproceso`, `detenido`.
