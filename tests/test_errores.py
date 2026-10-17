"""Rutas 9 y 10: errores transitorios (3 reintentos → cola) y de sistema (detener y alertar)."""

from gerald.errores import ErrorSistema, ErrorTransitorio
from gerald.graph import ejecutar_pedido, reprocesar
from tests.conftest import FakeInterprete


def test_transitorio_reintenta_tres_veces_y_encola(construir, nuevo_pedido):
    interprete = FakeInterprete(error=ErrorTransitorio("a2_boceto", "visión no disponible"))
    grafo, s = construir(interprete=interprete)
    pedido = nuevo_pedido()
    r = ejecutar_pedido(grafo, pedido, s)
    assert r["estado"] == "pendiente_reproceso"
    assert interprete.llamadas == 3
    pendiente = s.pedidos.pendientes[0]
    assert pendiente["pedido_id"] == pedido.pedido_id
    assert pendiente["carga"]["pedido"]["pedido_id"] == pedido.pedido_id  # carga completa


def test_reproceso_continua_desde_checkpoint(construir, nuevo_pedido):
    interprete = FakeInterprete(error=ErrorTransitorio("a2_boceto", "visión no disponible"))
    grafo, s = construir(interprete=interprete)
    pedido = nuevo_pedido()
    ejecutar_pedido(grafo, pedido, s)
    interprete.error = None  # el servicio se recuperó
    r = reprocesar(grafo, pedido.pedido_id, s)
    assert r["pausa"]["tipo"] == "aceptacion_cliente"
    assert len(s.pedidos.claves) == 1  # no se volvió a registrar


def test_error_de_sistema_detiene_y_alerta(construir, nuevo_pedido):
    grafo, s = construir(interprete=FakeInterprete(error=ErrorSistema("a2_boceto", "cuota agotada")))
    r = ejecutar_pedido(grafo, nuevo_pedido(), s)
    assert r["estado"] == "detenido"
    assert s.notificador.eventos()[-1] == "alerta"
    assert s.pedidos.pendientes == []


def test_tarea_de_reproceso_toma_la_cola(construir, nuevo_pedido):
    from gerald.tareas import reprocesar_pendientes

    interprete = FakeInterprete(error=ErrorTransitorio("a2_boceto", "visión no disponible"))
    grafo, s = construir(interprete=interprete)
    pedido = nuevo_pedido()
    ejecutar_pedido(grafo, pedido, s)
    interprete.error = None
    assert reprocesar_pendientes(grafo, s) == {pedido.pedido_id: "cotizado"}
    assert s.pedidos.pendientes == []  # recuperado: sale de la cola


def test_reproceso_agotado_alerta_y_detiene(construir, nuevo_pedido):
    from gerald.tareas import reprocesar_pendientes

    grafo, s = construir(interprete=FakeInterprete(error=ErrorTransitorio("a2_boceto", "caído")))
    pedido = nuevo_pedido()
    ejecutar_pedido(grafo, pedido, s)
    for _ in range(s.parametros.max_reprocesos - 1):
        assert reprocesar_pendientes(grafo, s) == {pedido.pedido_id: "pendiente_reproceso"}
    assert reprocesar_pendientes(grafo, s) == {pedido.pedido_id: "detenido"}
    assert s.notificador.eventos()[-1] == "alerta"
    assert len(s.pedidos.pendientes) == 1  # una sola fila por pedido, sin duplicados
    assert reprocesar_pendientes(grafo, s) == {}  # ya no se vuelve a tomar
