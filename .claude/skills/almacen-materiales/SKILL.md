---
name: almacen-materiales
description: Cómo el sistema consulta y usa el almacén de materiales (proveedores) de Gerald Sport — catálogo de telas e insumos con precios, recetas de consumo por prenda y talla, inventario, reservas transaccionales y requerimientos de abastecimiento. Úsala al trabajar con A3 Materiales, cálculo de costos, stock o faltantes.
---

# Almacén de materiales (proveedores)

En este proyecto **"proveedores" = el almacén**: la fuente de información de telas, insumos, precios y stock. No hay órdenes de compra a empresas externas en el alcance actual.

## Tablas
| Tabla | Contenido |
|---|---|
| `materiales` | catálogo: id, nombre, tipo (tela/insumo), unidad, precio_unitario_pen, activo |
| `recetas` | consumo por prenda y talla: prenda, talla, material_id, cantidad |
| `inventario` | material_id, disponible, reservado |
| `reservas` | pedido_id, material_id, cantidad, estado |
| `requerimientos_abastecimiento` | pedido_id, material_id, faltante, estado, fecha_estimada |

## Cálculo de materiales (A3)
```
para cada línea del pedido (prenda, talla, cantidad):
    para cada material de la receta:
        necesario += receta.cantidad × cantidad × (1 + merma_pct/100)
costo = Σ necesario × precio_unitario
```
- Redondear hacia arriba a la unidad mínima del material.
- Material inexistente o inactivo en el catálogo → `ErrorDatos` (observación al cliente: "color/tela no disponible").

## Reserva (después de la aceptación del cliente)
- Una sola transacción: `SELECT ... FOR UPDATE` sobre `inventario` de todos los materiales; si todo alcanza, incrementa `reservado` e inserta `reservas`.
- Si falta algo: reserva lo disponible, crea `requerimientos_abastecimiento` por el faltante y notifica al almacén. La única tarea humana es **abastecer material faltante**; al registrarse el ingreso, el flujo continúa y completa la reserva.
- Idempotente por `pedido_id`: repetir la reserva no duplica.

## Tools de A3 (y solo de A3)
`leer_catalogo`, `leer_recetas`, `consultar_stock`, `reservar_materiales`, `crear_requerimiento_abastecimiento`.
