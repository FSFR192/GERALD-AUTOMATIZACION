---
name: nuevo-subagente
description: Plantilla y pasos para crear o modificar un subagente (nodo LangGraph) de Gerald Sport con contrato Pydantic, servicios inyectados, manejo de errores por clase y registro en el grafo. Úsala al crear agents/aN_*.py o cambiar uno existente.
---

# Crear un subagente

## Patrón del proyecto
- Un nodo es una función `def nodo(state: GeraldState, servicios: Servicios) -> dict`.
- Los nodos **no** importan Postgres ni el LLM: usan los puertos de `gerald.servicios.Servicios`
  (`pedidos`, `almacen`, `notificador`, `interprete`, `evaluador`, `parametros`).
- `graph.construir_grafo()` liga `servicios` a cada nodo y le aplica `RetryPolicy`.
- Así las pruebas usan dobles en memoria y producción usa Postgres + LLM, sin cambiar el agente.

## Pasos
1. Confirma la responsabilidad única del agente y su elemento BPMN (`docs/MAPEO-BPMN.md`).
2. Define su contrato de salida en `src/gerald/schemas/resultados.py` (hereda de `ResultadoAgente`).
3. Si necesita infraestructura nueva, agrega un método al puerto en `servicios.py` y su
   implementación en `db/memoria.py` **y** `db/postgres.py` (o en su módulo de producción).
4. Crea `src/gerald/agents/aN_nombre.py` con la plantilla.
5. Regístralo en `NODOS` (o `PAUSAS` si usa `interrupt`) y conecta sus aristas en `graph.py`.
6. Agrega la clave de estado que escribe en `state.py` y en la tabla de P01.
7. Pruebas: camino feliz + cada ruta de error (skill `pruebas-flujo`).
8. Actualiza `docs/MAPEO-BPMN.md`.

## Plantilla de nodo

```python
"""AN Nombre: <responsabilidad en una línea>. BPMN: <tarea(s)>."""

from gerald.schemas.resultados import ResultadoNombre
from gerald.servicios import Servicios
from gerald.state import GeraldState

AGENTE = "aN_nombre"


def nodo(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    datos = servicios.almacen.algo(pedido.pedido_id)  # el puerto ya lanza errores clasificados
    resultado = ResultadoNombre.model_validate(datos)  # frontera Pydantic

    if resultado.observaciones:  # error de datos → observaciones
        return {"nombre": resultado, "observaciones": resultado.observaciones, "estado": "observado"}
    return {"nombre": resultado, "estado": "<nuevo_estado>"}  # solo sus claves
```

## Nodos con pausa humana
- Sin efectos secundarios antes de `interrupt()`: al reanudar, el nodo se ejecuta de nuevo desde el inicio.
- La notificación previa va en un nodo anterior de A4 (ej.: `solicitar_revision` → `revision_admin`).

## Si el agente usa un LLM
- Implementa la llamada como clase de producción del puerto (ej. `InterpreteVision`), no dentro del nodo.
- Obtén el modelo con `gerald.llm.get_llm(rol)` + `with_structured_output(Modelo)`.
- Invoca con `gerald.llm.invocar_con_errores()` para clasificar timeouts, 429 y cuotas.
- El contenido del cliente va en `<datos_cliente>` del mensaje de usuario, nunca en el system prompt.

## Lista de verificación
- [ ] Una sola responsabilidad
- [ ] Solo usa sus puertos/tools (P06)
- [ ] Salida validada con Pydantic
- [ ] Errores clasificados (P05)
- [ ] Prueba por ruta
- [ ] MAPEO-BPMN y P01 actualizados
