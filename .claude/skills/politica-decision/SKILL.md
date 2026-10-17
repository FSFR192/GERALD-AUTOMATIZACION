---
name: politica-decision
description: Reglas de la capa de decisión de Gerald Sport — decide() con salida estructurada y confianza (Sistema 1) y la política determinista que decide aprobación automática vs revisión del administrador. Úsala al cambiar umbrales, criterios de coherencia o la ruta de aprobación.
---

# Decisión y política

Referencia: `docs/protocolos/P03-decision-y-politica.md`.

## Separación de responsabilidades
- `decide()` (`decision/decide.py`): **evalúa** coherencia boceto–prenda–receta–costo y devuelve `Decision` con `coherente: bool`, `puntaje: 0..1`, `confianza: alta|media|baja`, `razones`.
- `politica.evaluar()` (`decision/politica.py`): **autoriza**. Es código puro, determinista, sin LLM.

## Política vigente
```
si no coherente                         → observaciones al cliente
si confianza == alta y costo ≤ umbral   → aprobación automática
en otro caso                            → revisión del administrador
```
Parámetros en tabla `parametros` (editables por el administrador, cacheados en `config`):
- `umbral_costo_pen` = 300.00
- `merma_pct` = 8
- `puntaje_minimo_alta` = 0.85, `puntaje_minimo_media` = 0.60

## Reglas
- La probabilidad del LLM **nunca** concede autorización por sí sola: `confianza` se recalcula a partir del `puntaje` con los umbrales de la tabla, no se toma literal del LLM.
- Respaldo: si el LLM falla, `decide()` aplica reglas fijas (recetas existentes, tallas válidas, costo dentro de rango histórico) y fija `confianza = baja`.
- Cambiar un umbral exige prueba que cubra ambos lados del límite.
- Toda decisión se guarda como etiqueta (bucle de calibración): `decision`, `veredicto`, resultado humano final.
