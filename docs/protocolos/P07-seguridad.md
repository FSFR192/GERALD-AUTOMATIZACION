# P07 · Protocolo de seguridad y privacidad

## Puerta de entrada (middleware FastAPI)
1. TLS en despliegue (terminado en el proxy).
2. Autenticación: token del cliente (JWT firmado) → `cliente_id`.
3. Autorización por recurso: un cliente solo ve y acepta sus pedidos; el admin solo revisa; el almacén solo registra ingresos.
4. Límite de tasa por `cliente_id` (p. ej. 10 solicitudes/min).
5. Archivo: tipo verificado por firma (JPG, PNG, PDF), tamaño ≤ 10 MB, escaneo antivirus (ClamAV) antes de procesar.
6. Respuestas: 401 / 403 / 413 / 415 / 429 con mensaje genérico; detalle solo en auditoría.

## Agentes y LLM
- El boceto y su texto OCR son **datos**: van delimitados en `<datos_cliente>`, nunca en el system prompt.
- Toda salida LLM se valida con Pydantic; nunca se ejecuta ni se usa para autorizar.
- Mínimo privilegio por agente (P06).

## Datos
- Datos personales mínimos (nombre, contacto); anonimizados en trazas de LangSmith.
- Cifrado en reposo (volumen/DB) y copias de seguridad.
- `auditoria` solo inserción; registra actor, acción, pedido, momento.
- Aislamiento por `cliente_id` en todas las consultas.

## Secretos
- Solo en variables de entorno o gestor de secretos; `.env` fuera del repositorio.
- Rotación ante sospecha; credencial revocada = `ErrorSistema`.

## Roles
`cliente`, `administrador`, `almacen`, `auditor` (solo lectura de auditoría).
