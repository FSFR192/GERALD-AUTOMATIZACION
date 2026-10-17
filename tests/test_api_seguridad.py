"""Puerta de seguridad (P07): autenticación, rol, tipo de archivo y flujo 1 clic desde la API."""

import json
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from gerald.api import main
from gerald.config import settings

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
DATOS = json.dumps({"lineas": [{"prenda": "polo", "talla": "M", "color": "azul", "cantidad": 10}]})


def token(rol: str, sub: str = "C-001") -> dict[str, str]:
    t = jwt.encode(
        {"sub": sub, "rol": rol, "correo": f"{sub}@x.pe", "exp": int(time.time()) + 600},
        settings().jwt_secreto.get_secret_value(),
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture
def cliente(construir, tmp_path, monkeypatch):
    grafo, servicios = construir()
    main.ESTADO.update(grafo=grafo, servicios=servicios)
    monkeypatch.setattr(settings(), "dir_bocetos", str(tmp_path))
    return TestClient(main.app), servicios  # sin `with`: no ejecuta el ciclo de vida de producción


def enviar(c, cabeceras, archivo=PNG):
    return c.post("/pedidos", headers=cabeceras, data={"datos": DATOS}, files={"archivo": ("b.png", archivo)})


def test_sin_token_401(cliente):
    c, _ = cliente
    assert c.post("/pedidos", data={"datos": DATOS}, files={"archivo": ("b.png", PNG)}).status_code == 401


def test_token_invalido_401(cliente):
    c, _ = cliente
    assert enviar(c, {"Authorization": "Bearer basura"}).status_code == 401


def test_rol_incorrecto_403(cliente):
    c, _ = cliente
    assert enviar(c, token("almacen")).status_code == 403


def test_archivo_no_permitido_415(cliente):
    c, _ = cliente
    assert enviar(c, token("cliente"), archivo=b"MZ\x90\x00ejecutable").status_code == 415


def test_datos_invalidos_400(cliente):
    c, _ = cliente
    r = c.post(
        "/pedidos",
        headers=token("cliente"),
        data={"datos": '{"lineas": []}'},
        files={"archivo": ("b.png", PNG)},
    )
    assert r.status_code == 400


def test_pedido_valido_y_aceptacion_un_clic(cliente):
    c, servicios = cliente
    r = enviar(c, token("cliente"))
    assert r.status_code == 202
    pedido_id = r.json()["pedido_id"]

    ver = c.get(f"/pedidos/{pedido_id}", headers=token("cliente"))
    assert ver.json()["pausa"]["tipo"] == "aceptacion_cliente"

    ajeno = c.post(
        f"/pedidos/{pedido_id}/aceptacion", headers=token("cliente", "C-999"), json={"acepta": True}
    )
    assert ajeno.status_code == 404  # un cliente no puede aceptar pedidos de otro

    r = c.post(f"/pedidos/{pedido_id}/aceptacion", headers=token("cliente"), json={"acepta": True})
    assert r.json()["estado"] == "en_produccion"


def test_ingreso_de_almacen_reanuda_pedidos_en_espera(construir, tmp_path, monkeypatch):
    from decimal import Decimal

    from tests.conftest import almacen_semilla

    grafo, servicios = construir(almacen=almacen_semilla(dryfit="5"))
    main.ESTADO.update(grafo=grafo, servicios=servicios)
    monkeypatch.setattr(settings(), "dir_bocetos", str(tmp_path))
    c = TestClient(main.app)

    pedido_id = enviar(c, token("cliente")).json()["pedido_id"]
    r = c.post(f"/pedidos/{pedido_id}/aceptacion", headers=token("cliente"), json={"acepta": True})
    assert r.json()["pausa"]["tipo"] == "abastecimiento"

    ingreso = {"material_id": "TEL-DRYFIT", "cantidad": "10"}
    assert c.post("/almacen/ingresos", headers=token("cliente"), json=ingreso).status_code == 403
    r = c.post("/almacen/ingresos", headers=token("almacen", "ALM-1"), json=ingreso)
    assert r.status_code == 200
    assert r.json()[pedido_id]["estado"] == "en_produccion"
    assert servicios.almacen.disponible["TEL-DRYFIT"] == Decimal("2.04")
