"""A3 Materiales: todo lo que toca el almacén (proveedores).
BPMN: Calcular materiales y costo / Verificar disponibilidad / Generar requerimiento de
abastecimiento / Reservar materiales.
"""

from collections import defaultdict
from decimal import ROUND_CEILING, Decimal

from gerald.schemas.resultados import CalculoMateriales, Faltante, LineaMaterial, Reserva
from gerald.servicios import Servicios
from gerald.state import GeraldState

AGENTE = "a3_materiales"
CENTESIMO = Decimal("0.01")
UNIDAD = Decimal("1")


def calcular(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    merma = Decimal(1) + servicios.parametros.merma_pct / Decimal(100)
    necesario: dict[str, Decimal] = defaultdict(Decimal)
    observaciones: list[str] = []

    for linea in pedido.lineas:
        receta = servicios.almacen.receta(linea.prenda.lower(), linea.talla)
        if not receta:
            observaciones.append(
                f"No tenemos receta para '{linea.prenda}' en talla {linea.talla}. "
                "Elija otra prenda o talla del catálogo."
            )
            continue
        for material_id, cantidad_unitaria in receta:
            necesario[material_id] += cantidad_unitaria * linea.cantidad * merma

    catalogo = servicios.almacen.materiales(list(necesario))
    lineas: list[LineaMaterial] = []
    for material_id, cantidad in necesario.items():
        material = catalogo.get(material_id)
        if material is None or not material.activo:
            observaciones.append(f"El material {material_id} no está disponible en el catálogo.")
            continue
        # Las unidades enteras (cierres, conos de hilo) no se compran en fracciones.
        paso = UNIDAD if material.unidad == "und" else CENTESIMO
        cantidad = cantidad.quantize(paso, rounding=ROUND_CEILING)
        lineas.append(
            LineaMaterial(
                material_id=material_id,
                nombre=material.nombre,
                unidad=material.unidad,
                cantidad=cantidad,
                precio_unitario_pen=material.precio_unitario_pen,
                subtotal_pen=(cantidad * material.precio_unitario_pen).quantize(CENTESIMO),
            )
        )

    calculo = CalculoMateriales(
        lineas=lineas,
        costo_total_pen=sum((linea.subtotal_pen for linea in lineas), Decimal("0")),
        observaciones=observaciones,
        evidencias=[f"merma aplicada: {servicios.parametros.merma_pct} %"],
    )
    if observaciones:
        return {"calculo": calculo, "observaciones": observaciones, "estado": "observado"}
    return {"calculo": calculo, "estado": "calculado"}


def verificar_stock(state: GeraldState, servicios: Servicios) -> dict:
    requeridos = state["calculo"].requeridos()
    stock = servicios.almacen.stock(list(requeridos))
    suficiente = all(stock.get(mid, Decimal(0)) >= cant for mid, cant in requeridos.items())
    return {"stock_suficiente": suficiente}


def requerir_abastecimiento(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    requeridos = state["calculo"].requeridos()
    stock = servicios.almacen.stock(list(requeridos))
    faltantes = {
        mid: cant - stock.get(mid, Decimal(0))
        for mid, cant in requeridos.items()
        if stock.get(mid, Decimal(0)) < cant
    }
    servicios.almacen.crear_requerimiento(pedido.pedido_id, faltantes)
    servicios.notificador.enviar(
        "abastecimiento",
        servicios.correo_almacen,
        pedido.pedido_id,
        {"faltantes": {k: str(v) for k, v in faltantes.items()}},
    )
    servicios.pedidos.actualizar_estado(pedido.pedido_id, "esperando_abastecimiento")
    return {"estado": "esperando_abastecimiento"}


def reservar(state: GeraldState, servicios: Servicios) -> dict:
    pedido = state["pedido"]
    faltantes = servicios.almacen.reservar(pedido.pedido_id, state["calculo"].requeridos())
    reserva = Reserva(
        completa=not faltantes,
        faltantes=[Faltante(material_id=k, cantidad=v) for k, v in faltantes.items()],
    )
    if reserva.completa:
        servicios.pedidos.actualizar_estado(pedido.pedido_id, "reservado")
        return {"reserva": reserva, "estado": "reservado"}
    return {"reserva": reserva, "stock_suficiente": False}
