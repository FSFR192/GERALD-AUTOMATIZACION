"""Portal web: endpoints de la interfaz, aislamiento por cliente (P07) y login demo solo en modo demo."""

from fastapi.testclient import TestClient

from gerald.api import main
from gerald.config import settings
from tests.conftest import almacen_semilla
from tests.test_api_seguridad import PNG, enviar, token


def _cliente(construir, tmp_path, monkeypatch, **kw):
    grafo, servicios = construir(**kw)
    main.ESTADO.update(grafo=grafo, servicios=servicios)
    monkeypatch.setattr(settings(), "dir_bocetos", str(tmp_path))
    return TestClient(main.app), servicios


def test_portal_se_sirve_y_raiz_redirige(construir, tmp_path, monkeypatch):
    c, _ = _cliente(construir, tmp_path, monkeypatch)
    assert "Portal de pedidos" in c.get("/app/").text
    assert c.get("/app/app.js").status_code == 200
    assert c.get("/", follow_redirects=False).headers["location"] == "/app/"


def test_catalogo_requiere_sesion(construir, tmp_path, monkeypatch):
    c, _ = _cliente(construir, tmp_path, monkeypatch)
    assert c.get("/catalogo").status_code == 401
    assert c.get("/catalogo", headers=token("cliente")).json()["prendas"]["polo"] == ["S", "M", "L", "XL"]


def test_mis_pedidos_y_boceto_aislados_por_cliente(construir, tmp_path, monkeypatch):
    c, _ = _cliente(construir, tmp_path, monkeypatch)
    pid = enviar(c, token("cliente")).json()["pedido_id"]

    mios = c.get("/pedidos", headers=token("cliente")).json()["pedidos"]
    assert [p["pedido_id"] for p in mios] == [pid]
    assert mios[0]["costo_total_pen"] is not None
    assert "materiales" not in mios[0]  # precios del almacén solo para el administrador
    assert c.get("/pedidos", headers=token("cliente", "C-999")).json()["pedidos"] == []

    assert c.get(f"/pedidos/{pid}/boceto", headers=token("cliente")).content == PNG
    assert c.get(f"/pedidos/{pid}/boceto", headers=token("cliente", "C-999")).status_code == 404
    assert c.get(f"/pedidos/{pid}/boceto", headers=token("administrador", "ADM-1")).status_code == 200
    admin = c.get(f"/pedidos/{pid}", headers=token("administrador", "ADM-1")).json()
    assert admin["materiales"][0]["material_id"] == "TEL-DRYFIT"


def test_bandeja_incluye_detalle_para_revisar(construir, tmp_path, monkeypatch):
    from tests.conftest import FakeEvaluador

    c, _ = _cliente(construir, tmp_path, monkeypatch, evaluador=FakeEvaluador(puntaje=0.7))
    pid = enviar(c, token("cliente")).json()["pedido_id"]
    bandeja = c.get("/revision", headers=token("administrador", "ADM-1")).json()
    assert bandeja["en_revision"] == [pid]
    assert "confianza media" in bandeja["pedidos"][0]["motivo"]
    assert bandeja["pedidos"][0]["materiales"]


def test_requerimientos_del_almacen(construir, tmp_path, monkeypatch):
    c, _ = _cliente(construir, tmp_path, monkeypatch, almacen=almacen_semilla(dryfit="5"))
    pid = enviar(c, token("cliente")).json()["pedido_id"]
    c.post(f"/pedidos/{pid}/aceptacion", headers=token("cliente"), json={"acepta": True})
    assert c.get("/almacen/requerimientos", headers=token("cliente")).status_code == 403
    reqs = c.get("/almacen/requerimientos", headers=token("almacen", "ALM-1")).json()["requerimientos"]
    assert reqs == [
        {
            "pedido_id": pid,
            "material_id": "TEL-DRYFIT",
            "faltante": "7.96",
            "nombre": "Tela dry-fit",
            "unidad": "m",
            "stock": "5",
        }
    ]


def test_login_demo_solo_en_modo_demo(construir, tmp_path, monkeypatch):
    c, _ = _cliente(construir, tmp_path, monkeypatch)
    monkeypatch.setattr(settings(), "modo", "produccion")
    assert c.post("/demo/sesion", json={"rol": "administrador", "id": "X-1"}).status_code == 404
    monkeypatch.setattr(settings(), "modo", "demo")
    r = c.post("/demo/sesion", json={"rol": "administrador", "id": "ADM-1"})
    assert c.get("/revision", headers={"Authorization": "Bearer " + r.json()["token"]}).status_code == 200
    assert c.post("/demo/sesion", json={"rol": "superusuario", "id": "X-1"}).status_code == 422


def test_actividad_muestra_cada_agente_en_orden(construir, tmp_path, monkeypatch):
    c, _ = _cliente(construir, tmp_path, monkeypatch, almacen=almacen_semilla(dryfit="5"))
    pid = enviar(c, token("cliente")).json()["pedido_id"]
    c.post(f"/pedidos/{pid}/aceptacion", headers=token("cliente"), json={"acepta": True})

    cli = c.get(f"/pedidos/{pid}", headers=token("cliente")).json()["actividad"]
    assert [p["agente"] for p in cli] == [
        "A0 Ingesta",
        "A1 Recepción",
        "A2 Boceto",
        "A3 Materiales",
        "Orquestador",
        "A4 Registro",
        "Cliente",
        "A4 Registro",
        "A3 Materiales",
        "A3 Materiales",
        "Almacén",
    ]
    assert cli[-1]["estado"] == "esperando" and "almacén" in cli[-1]["detalle"]
    evaluacion = next(p for p in cli if p["agente"] == "Orquestador")["detalle"]
    assert "puntaje" not in evaluacion  # el cliente no ve puntajes internos

    adm = c.get(f"/pedidos/{pid}", headers=token("administrador", "ADM-1")).json()["actividad"]
    assert "puntaje 0.95" in next(p for p in adm if p["agente"] == "Orquestador")["detalle"]


def test_pedido_detenido_se_muestra_detenido(construir, tmp_path, monkeypatch):
    from gerald.errores import ErrorSistema
    from tests.conftest import FakeInterprete

    error = ErrorSistema("a2_boceto", "el modelo configurado no existe o fue retirado")
    c, _ = _cliente(construir, tmp_path, monkeypatch, interprete=FakeInterprete(error=error))
    pid = enviar(c, token("cliente")).json()["pedido_id"]
    p = c.get(f"/pedidos/{pid}", headers=token("cliente")).json()
    assert p["estado"] == "detenido"
    assert p["actividad"][-1]["agente"] == "A2 Boceto"
    assert p["actividad"][-1]["estado"] == "error"
