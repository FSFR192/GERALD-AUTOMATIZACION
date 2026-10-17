---
name: contratos-pydantic
description: Reglas para definir los contratos de datos de Gerald Sport con Pydantic v2 (pedido de entrada, resultados de agentes, decisiones, eventos). Úsala al crear o cambiar modelos en src/gerald/schemas/ o al validar salidas de LLM.
---

# Contratos Pydantic

## Principios
- `model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)` en modelos de entrada y resultados.
- Montos en `Decimal` con 2 decimales y moneda explícita (`PEN`). Nunca `float` para dinero.
- Cantidades de material en `Decimal` con su `unidad` (m, m2, kg, und).
- Enumeraciones (`Literal` o `Enum`) para estados, tallas y niveles de confianza.
- Toda salida de LLM se valida con su modelo; si falla, es `ErrorDatos` del agente (no se reintenta igual).
- Versiona los contratos que salen del sistema (`version: Literal["1.0"]`).

## Modelos base existentes (`schemas/`)
| Modelo | Uso |
|---|---|
| `PedidoEntrada` | cuerpo del webhook / formulario |
| `ResultadoAgente` | base: `agente`, `confianza`, `evidencias`, `observaciones` |
| `InterpretacionBoceto` | salida A2 |
| `CalculoMateriales` | salida A3 (líneas + costo total) |
| `Decision` | salida de `decide()` |
| `VeredictoPolitica` | salida de `politica.evaluar()` |
| `Reserva` | resultado de reservar materiales |

## Ejemplo de validación de LLM

```python
llm = get_llm(rol="vision").with_structured_output(InterpretacionBoceto)
resultado = llm.invoke(mensajes)  # ya es InterpretacionBoceto o lanza error
```

## Cambios de contrato
Si cambias un campo usado por otro agente: actualiza P02 y avisa en el resumen del cambio.
