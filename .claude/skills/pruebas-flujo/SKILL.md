---
name: pruebas-flujo
description: Cómo probar los flujos del BPMN TO-BE de Gerald Sport con pytest — fixtures, LLM simulado, almacén semilla, ejecución hasta interrupt y reanudación, y verificación de rutas de error. Úsala al escribir o correr pruebas en tests/.
---

# Pruebas de flujo

## Matriz obligatoria (una prueba por ruta)
| # | Ruta BPMN | Archivo |
|---|---|---|
| 1 | Camino feliz con aprobación automática y stock suficiente | `test_flujo_feliz.py` |
| 2 | Datos incompletos → observaciones al cliente | `test_observaciones.py` |
| 3 | Pedido duplicado → descartado | `test_duplicados.py` |
| 4 | Boceto incoherente → observaciones | `test_observaciones.py` |
| 5 | Confianza media/costo alto → revisión admin → aprobado | `test_hitl.py` |
| 6 | Revisión admin → rechazado → observaciones | `test_hitl.py` |
| 7 | Cliente no acepta → pedido no contratado | `test_aceptacion.py` |
| 8 | Stock insuficiente → requerimiento → abastecido → reserva | `test_almacen.py` |
| 9 | Error transitorio → 3 reintentos → cola de pendientes → reproceso | `test_errores.py` |
| 10 | Error de sistema → alerta → flujo detenido | `test_errores.py` |
| 11 | Política: límites del umbral (299.99 / 300.00 / 300.01) | `test_politica.py` |

## Fixtures (`tests/conftest.py`)
- `FakeInterprete` / `FakeEvaluador`: dobles del LLM (visión y decide); configurables para ilegible,
  incoherente, puntaje o para lanzar `ErrorTransitorio` / `ErrorSistema`. Nunca hay red.
- `almacen_semilla(dryfit=...)`: catálogo, recetas e inventario mínimos (stock configurable).
- `construir(interprete=, evaluador=, almacen=)`: devuelve `(grafo, servicios)` con `MemorySaver` y
  reintentos rápidos; `servicios` expone los repositorios en memoria para verificar efectos.
- `nuevo_pedido(cantidad=, talla=, prenda=)`: pedido válido de un polo.

## Patrón HITL
```python
grafo, s = construir()
r = ejecutar_pedido(grafo, nuevo_pedido(cantidad=30), s)  # costo > umbral
assert r["pausa"]["tipo"] == "revision_admin"
r = reanudar(grafo, pedido_id, {"aprobado": True}, s)
```

## Comando
`uv run pytest -q` — todas deben pasar antes de cerrar una tarea.
