# Mapeo BPMN TO-BE → implementación

Fuente: `docs/bpmn/TO-BE_GeraldSport_Previo.bpmn`. Toda fila debe tener prueba (`/verificar-flujo`).

| Carril | Elemento BPMN | Tipo | Implementación | Prueba |
|---|---|---|---|---|
| Cliente | Enviar pedido con boceto, tallas, colores y cantidad | Tarea usuario | `POST /pedidos` (`api/main.py`) | test_flujo_feliz |
| Sistema | Recibir y validar el pedido | Servicio | middleware `api/seguridad.py` + `agents/a0_ingesta.nodo` | test_observaciones |
| Sistema | ¿Datos completos y válidos? | Gateway | `graph.ruta_si_observado` | test_observaciones |
| Sistema | Verificar si el pedido ya fue registrado | Servicio | `agents/a1_recepcion.nodo` | test_duplicados |
| Sistema | ¿Pedido duplicado? / Informar que ya existe | Gateway / Envío | `graph.ruta_tras_recepcion` → `a4_registro.informar_duplicado` | test_duplicados |
| Sistema | Registrar pedido y confirmar recepción | Envío | `a1_recepcion.nodo` (registro y acuse) | test_flujo_feliz |
| Sistema | Interpretar el boceto | Servicio | `agents/a2_boceto.nodo` | test_flujo_feliz |
| Sistema | Calcular materiales y costo con el catálogo | Servicio | `agents/a3_materiales.calcular` (merma; `und` redondeado a entero) + semilla `db/semilla.py` | test_flujo_feliz, test_semilla |
| Sistema | Evaluar coherencia y nivel de confianza | Regla de negocio | `decision/decide.decide` | test_observaciones |
| Sistema | ¿Pedido coherente? / ¿Confianza alta y costo dentro del umbral? | Gateways | `decision/politica.evaluar` + `graph.ruta_tras_politica` | test_politica |
| Sistema | Enviar observaciones precisas al cliente | Envío | `a4_registro.enviar_observaciones` | test_observaciones |
| Admin | Revisar y aprobar propuesta | Usuario (HITL) | `agents/orquestador.revision_admin` (`interrupt`) | test_hitl |
| Admin | 24 h sin revisión → recordar y escalar | Temporizador | `tareas.vigilar_sla` | test_aceptacion |
| Sistema | Generar y enviar cotización y contrato | Envío | `a4_registro.cotizar` | test_flujo_feliz |
| Cliente | Aceptar cotización y contrato (1 clic) | Usuario (HITL) | `agents/orquestador.aceptacion_cliente` (`interrupt`) | test_aceptacion |
| Cliente | 48 h sin respuesta → recordatorio | Temporizador | `tareas.vigilar_sla` | test_aceptacion |
| Sistema | Registrar contrato del pedido | Servicio | `a4_registro.registrar_contrato` | test_flujo_feliz |
| Sistema | Verificar disponibilidad de materiales | Servicio | `a3_materiales.verificar_stock` | test_almacen |
| Sistema | Generar requerimiento de abastecimiento | Envío | `a3_materiales.requerir_abastecimiento` | test_almacen |
| Almacén | Abastecer material faltante | Usuario (HITL) | `POST /almacen/ingresos` (`RepoAlmacen.ingresar` → pedidos atendidos) → `orquestador.espera_abastecimiento` | test_almacen, test_api_seguridad |
| Sistema | Reservar materiales para el pedido | Servicio | `a3_materiales.reservar` | test_almacen |
| Sistema | Generar lista de materiales y orden de producción | Servicio | `a4_registro.generar_orden` + hoja CSV (`tools/notificacion.hoja_materiales`) en el aviso al admin | test_flujo_feliz, test_tools |
| Sistema | Notificar fecha estimada | Envío | `a4_registro.notificar_confirmacion` | test_flujo_feliz |
| Sistema | Eventos de error (5) | Límite error | `errores.py` + `RetryPolicy` + `graph._ejecutar` + `tareas.reprocesar_pendientes` | test_errores |

## Elementos de la arquitectura fuera del BPMN

| Capa (diagrama de arquitectura) | Implementación | Prueba |
|---|---|---|
| Herramientas @tool por agente (P06) | `tools/__init__.tools_de` + `tools/{recepcion,vision,almacen,notificacion}.py` | test_tools |
| Traza del sistema multiagente (qué agente hizo qué) | `traza.traza` desde los checkpoints de LangGraph → `actividad` en `GET /pedidos/{id}` y en el portal | test_portal |
| Bucle de calibración | `calibracion.informe` · `tareas.calibracion_semanal` · `GET /calibracion` | test_calibracion |
| Gobernanza LangSmith | `observabilidad.configurar_trazas` (entradas/salidas ocultas) · metadatos por pedido | test_demo |
| Libro de reglas (7 materiales, 14 recetas, parámetros) | `db/semilla.py` → `db/init.py` · `db/postgres.cargar_parametros` | test_semilla, test_postgres |
| Modo demo sin Postgres | `demo.py` (`GERALD_MODO=demo`) · `POST /demo/sesion` (solo demo) | test_demo, test_portal |
| Portal de pedidos (interfaz por carril) | `web/` servido en `/app`: Cliente (nuevo pedido, mis pedidos, aceptación 1 clic), Administrador (bandeja con boceto y borrador), Almacén (faltantes), Gobernanza (calibración) · `GET /pedidos`, `/catalogo`, `/pedidos/{id}/boceto`, `/almacen/requerimientos` | test_portal |
