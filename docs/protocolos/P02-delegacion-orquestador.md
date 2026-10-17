# P02 · Protocolo de delegación (orquestador ↔ subagentes)

## Roles

| Agente | Responsabilidad única | Usa LLM | BPMN |
|---|---|---|---|
| **GERALD-ORCH** (orquestador) | Planificar la ruta, aplicar `decide()` y la política, gestionar pausas HITL y estados | Sí (decide) | Evaluar coherencia; decisiones; generar cotización |
| **A0 Ingesta** | Validar el contrato de datos del pedido | No | Recibir y validar el pedido |
| **A1 Recepción** | Clave SHA-256, deduplicar, registrar y acusar recibo | No | Verificar duplicado; registrar pedido |
| **A2 Boceto** | Interpretar el boceto (visión + OCR) | Sí (visión) | Interpretar el boceto |
| **A3 Materiales** | Calcular consumo y costo con el almacén; verificar stock; reservar; requerir abastecimiento | No (reglas) | Calcular materiales; verificar disponibilidad; reservar; requerimiento |
| **A4 Registro** | Registrar contrato, generar documentos y notificar | Opcional (redacción) | Observaciones; cotización; contrato; lista y orden; notificación |

## Contrato de resultado

Todo subagente devuelve un modelo que hereda de:

```python
class ResultadoAgente(BaseModel):
    agente: str
    confianza: Literal["alta", "media", "baja"] = "alta"
    evidencias: list[str] = []
    observaciones: list[str] = []  # mensajes accionables para el cliente
```

## Reglas de delegación
1. El orquestador **no** ejecuta tools de dominio; solo enruta y decide.
2. Un subagente **no** decide el siguiente paso: deja su resultado en el estado y el orquestador enruta con aristas condicionales.
3. Las observaciones deben ser **específicas y accionables** ("La talla XXL no existe en el catálogo; elija entre S–XL"), nunca genéricas.
4. Si un subagente no puede completar con certeza, baja `confianza` y explica en `evidencias`; no inventa datos.
5. Orden normal: A0 → A1 → A2 → A3 (cálculo) → decide → política → [admin] → A4 (cotización) → [cliente] → A4 (contrato) → A3 (stock/reserva) → A4 (orden y notificación).
