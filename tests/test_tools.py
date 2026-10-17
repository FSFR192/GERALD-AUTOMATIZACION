"""P06: cada agente recibe solo sus tools; entradas validadas antes de tocar la infraestructura."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from gerald.agents.a1_recepcion import clave_idempotencia
from gerald.errores import ErrorSistema
from gerald.tools import tools_de
from gerald.tools.notificacion import hoja_materiales

ESPERADO = {
    "a1_recepcion": {"calcular_hash", "buscar_pedido_por_clave", "encolar_pendiente"},
    "a2_boceto": {"interpretar_boceto", "extraer_texto_ocr"},
    "a3_materiales": {
        "leer_catalogo",
        "leer_recetas",
        "consultar_stock",
        "reservar_materiales",
        "crear_requerimiento_abastecimiento",
        "leer_parametros",
    },
    "a4_registro": {"enviar_correo", "generar_hoja_materiales", "registrar_contrato"},
    "orquestador": {"leer_parametros"},
}


def _por_nombre(agente, servicios):
    return {t.name: t for t in tools_de(agente, servicios)}


def test_minimo_privilegio_por_agente(construir):
    _, s = construir()
    for agente, nombres in ESPERADO.items():
        assert set(_por_nombre(agente, s)) == nombres, agente
    assert tools_de("a0_ingesta", s) == []  # A0 no usa tools
    # ninguna tool compartida salvo leer_parametros (A3 y orquestador, según P06)
    a = [n for ag, ns in ESPERADO.items() if ag != "orquestador" for n in ns]
    assert len(a) == len(set(a))


def test_tools_a1(construir, nuevo_pedido):
    _, s = construir()
    t = _por_nombre("a1_recepcion", s)
    pedido = nuevo_pedido()
    clave = t["calcular_hash"].invoke({"pedido": pedido})
    assert clave == clave_idempotencia(pedido)
    assert t["buscar_pedido_por_clave"].invoke({"clave": clave}) is None
    s.pedidos.registrar(pedido, clave)
    assert t["buscar_pedido_por_clave"].invoke({"clave": clave}) == pedido.pedido_id
    t["encolar_pendiente"].invoke({"pedido": pedido, "motivo": "visión caída"})
    assert s.pedidos.pendientes[0]["pedido_id"] == pedido.pedido_id
    with pytest.raises(ValidationError):
        t["buscar_pedido_por_clave"].invoke({"clave": "'; DROP TABLE pedidos; --"})


def test_tools_a2_ocr_no_configurado_es_error_de_sistema(construir, nuevo_pedido):
    _, s = construir()
    t = _por_nombre("a2_boceto", s)
    assert t["interpretar_boceto"].invoke({"pedido": nuevo_pedido()})["prenda"] == "polo"
    with pytest.raises(ErrorSistema):
        t["extraer_texto_ocr"].invoke({"pedido": nuevo_pedido()})
    s.ocr = lambda pedido: ["GERALD", "10"]
    assert _por_nombre("a2_boceto", s)["extraer_texto_ocr"].invoke({"pedido": nuevo_pedido()}) == [
        "GERALD",
        "10",
    ]


def test_tools_a3_reserva_y_requerimiento(construir):
    _, s = construir()
    t = _por_nombre("a3_materiales", s)
    assert t["leer_recetas"].invoke({"prenda": "polo", "talla": "M"})[0]["material_id"] == "TEL-DRYFIT"
    assert t["reservar_materiales"].invoke({"pedido_id": "P-1", "cantidades": {"TEL-DRYFIT": "500"}}) == {
        "TEL-DRYFIT": "300"
    }
    assert t["reservar_materiales"].invoke({"pedido_id": "P-1", "cantidades": {"TEL-DRYFIT": "50"}}) == {}
    assert s.almacen.disponible["TEL-DRYFIT"] == Decimal("150")
    t["crear_requerimiento_abastecimiento"].invoke({"pedido_id": "P-2", "cantidades": {"INS-HILO": "5"}})
    assert s.almacen.requerimientos[-1]["pedido_id"] == "P-2"
    assert t["leer_parametros"].invoke({})["umbral_costo_pen"] == "300.00"
    with pytest.raises(ValidationError):
        t["leer_recetas"].invoke({"prenda": "polo", "talla": "XXXL"})


def test_tools_a4_correo_y_hoja(construir):
    _, s = construir()
    t = _por_nombre("a4_registro", s)
    t["enviar_correo"].invoke({"evento": "recordatorio", "destinatario": "c@x.pe", "pedido_id": "P-1"})
    assert s.notificador.eventos() == ["recordatorio"]
    with pytest.raises(ValidationError):  # solo eventos con plantilla (P08)
        t["enviar_correo"].invoke({"evento": "phishing", "destinatario": "c@x.pe", "pedido_id": "P-1"})


def test_hoja_materiales_csv():
    from gerald.schemas.resultados import LineaMaterial

    linea = LineaMaterial(
        material_id="TEL-DRYFIT",
        nombre="Tela dry-fit",
        unidad="m",
        cantidad=Decimal("12.96"),
        precio_unitario_pen=Decimal("12.50"),
        subtotal_pen=Decimal("162.00"),
    )
    filas = hoja_materiales("P-1", [linea]).strip().splitlines()
    assert filas[0].startswith("pedido,material")
    assert filas[-1].endswith("162.00")
