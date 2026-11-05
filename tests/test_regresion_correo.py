"""Regresión: un correo caído marcaba como "duplicado" a pedidos nuevos y detenía el flujo.

Causa: A1 registraba el pedido, el acuse por correo fallaba (ErrorTransitorio), RetryPolicy repetía A1
y este encontraba su propia clave → "duplicado". Ahora A1 reconoce su propio registro y el correo
caído no bloquea a los agentes (P08).
"""

from gerald.errores import ErrorTransitorio
from gerald.graph import ejecutar_pedido
from gerald.notificaciones import NotificadorCorreo


class NotificadorQueFallaUnaVez:
    def __init__(self):
        self.enviados, self.fallos = [], 0

    def enviar(self, evento, destinatario, pedido_id, datos):
        if self.fallos == 0:
            self.fallos += 1
            raise ErrorTransitorio("notificacion", "servidor de correo no disponible")
        self.enviados.append(evento)


def test_reintento_de_a1_no_es_duplicado(construir, nuevo_pedido):
    grafo, s = construir()
    s.notificador = NotificadorQueFallaUnaVez()
    r = ejecutar_pedido(grafo, nuevo_pedido(), s)
    assert r["estado"] == "cotizado"
    assert r["pausa"]["tipo"] == "aceptacion_cliente"
    assert [a["accion"] for a in s.pedidos.auditoria].count("registrar_pedido") == 1


def test_duplicado_real_sigue_detectandose(construir, nuevo_pedido):
    grafo, s = construir()
    original = nuevo_pedido()
    ejecutar_pedido(grafo, original, s)
    copia = original.model_copy(update={"pedido_id": "P-COPIA"})
    assert ejecutar_pedido(grafo, copia, s)["estado"] == "duplicado"


def test_correo_caido_no_detiene_el_flujo_y_queda_en_bandeja(construir, nuevo_pedido):
    grafo, s = construir()
    s.notificador = NotificadorCorreo(host="127.0.0.1:1")  # puerto sin servidor SMTP
    r = ejecutar_pedido(grafo, nuevo_pedido(), s)
    assert r["pausa"]["tipo"] == "aceptacion_cliente"  # el cliente acepta desde el portal
    assert {e[0] for e in s.notificador.bandeja_salida} >= {"recepcion", "cotizacion"}
    assert s.notificador.reintentar_pendientes() == 0  # sigue caído: se conservan
    assert s.notificador.bandeja_salida
