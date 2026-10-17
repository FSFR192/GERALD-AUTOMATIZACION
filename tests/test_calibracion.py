"""Bucle de calibración (P03): confianza vs resultado, deriva y sugerencias que no se aplican solas."""

import typing

from gerald.calibracion import informe
from gerald.config import Parametros
from gerald.graph import ejecutar_pedido, reanudar
from gerald.notificaciones import PLANTILLAS
from gerald.tareas import calibracion_semanal
from gerald.tools.notificacion import Evento


def _etiquetas(confianza: str, contratados: int, fallidos: int) -> list[dict]:
    return [{"confianza": confianza, "resultado": "contratado"}] * contratados + [
        {"confianza": confianza, "resultado": "no_contratado"}
    ] * fallidos


def test_sin_deriva_con_alta_sana():
    r = informe(_etiquetas("alta", 39, 1), Parametros())
    assert r.por_confianza["alta"].tasa_fallo == 0.025
    assert r.deriva is False


def test_deriva_sugiere_subir_umbral():
    r = informe(_etiquetas("alta", 18, 4), Parametros())
    assert r.deriva is True
    assert "0.9" in r.sugerencias[0]


def test_muestra_pequena_no_concluye():
    r = informe(_etiquetas("alta", 1, 4), Parametros())
    assert r.deriva is False
    assert "Muestra insuficiente" in r.sugerencias[-1]


def test_media_casi_siempre_aprobada_sugiere_bajar_umbral():
    etiquetas = (
        _etiquetas("alta", 25, 0)
        + [{"confianza": "media", "aprobado_admin": True, "resultado": "contratado"}] * 20
    )
    assert "bajar puntaje_minimo_alta" in informe(etiquetas, Parametros()).sugerencias[0]


def test_rechazo_admin_cuenta_como_fallo():
    r = informe([{"confianza": "media", "aprobado_admin": False, "resultado": "observado"}], Parametros())
    assert r.por_confianza["media"].fallidos == 1


def test_tarea_semanal_alerta_deriva_y_no_toca_parametros(construir):
    _, s = construir()
    s.pedidos.etiquetas_registradas.extend(_etiquetas("alta", 15, 5))
    antes = s.parametros.model_copy()
    r = calibracion_semanal(s)
    assert r.deriva and s.notificador.eventos() == ["calibracion"]
    assert s.parametros == antes


def test_etiquetas_del_flujo_alimentan_el_informe(construir, nuevo_pedido):
    grafo, s = construir()
    p = nuevo_pedido()
    ejecutar_pedido(grafo, p, s)
    reanudar(grafo, p.pedido_id, {"acepta": True}, s)
    r = calibracion_semanal(s)
    assert r.por_confianza["alta"].contratados == 1


def test_eventos_de_la_tool_coinciden_con_plantillas():
    assert set(typing.get_args(Evento)) == set(PLANTILLAS)
