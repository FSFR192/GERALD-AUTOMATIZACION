# P06 · Protocolo de herramientas (@tool) y mínimo privilegio

Cada tool pertenece a **un** agente. Importarla desde otro agente es una violación.
El único punto de entrega es `gerald.tools.tools_de(agente, servicios)`; `tests/test_tools.py` verifica esta tabla.

| Tool | Agente dueño | Lee / Escribe | Fuente |
|---|---|---|---|
| `calcular_hash` | A1 | — | memoria |
| `buscar_pedido_por_clave` | A1 | Lee `pedidos` | PostgreSQL |
| `encolar_pendiente` | A1 | Escribe `cola_pendientes` | PostgreSQL |
| `interpretar_boceto` | A2 | — | LLM visión |
| `extraer_texto_ocr` | A2 | — | OCR (puerto `Ocr`, `OcrVision`) |
| `leer_catalogo` | A3 | Lee `materiales` | Almacén |
| `leer_recetas` | A3 | Lee `recetas` | Almacén |
| `leer_parametros` | A3, orquestador | Lee `parametros` | PostgreSQL |
| `consultar_stock` | A3 | Lee `inventario` | Almacén |
| `reservar_materiales` | A3 | Escribe `inventario`, `reservas` | Almacén (transacción) |
| `crear_requerimiento_abastecimiento` | A3 | Escribe `requerimientos_abastecimiento` | Almacén |
| `registrar_contrato` | A4 | Escribe `contratos` | PostgreSQL |
| `generar_hoja_materiales` | A4 | — (devuelve CSV) | memoria |
| `enviar_correo` | A4 | — | SMTP/API correo |
| `registrar_auditoria` | todos vía `gerald.db.auditoria` | Inserta `auditoria` | PostgreSQL |

## Requisitos de cada tool
1. `args_schema` Pydantic.
2. Timeout ≤ 5 s (DB) / ≤ 30 s (LLM visión).
3. Errores clasificados según P05.
4. Escrituras idempotentes.
5. Credenciales por variable de entorno, con el rol de base de datos más restringido posible.

## MCP (opcional, fase 4)
Si se exponen las tools por MCP, cada servidor MCP agrupa las tools de un solo agente (p. ej. `mcp-almacen` solo para A3).
