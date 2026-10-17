"""API REST de Gerald Sport. Puntos de contacto humanos: crear pedido, aceptar, revisar, abastecer."""

import hashlib
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, ValidationError

from gerald.api.seguridad import Usuario, limitar, requerir_rol, validar_archivo
from gerald.calibracion import informe
from gerald.config import settings
from gerald.graph import construir_grafo, ejecutar_pedido, reanudar, resumen
from gerald.observabilidad import configurar_trazas
from gerald.schemas.pedido import DatosPedido, PedidoEntrada
from gerald.servicios import Servicios

ESTADO: dict = {}


def construir_servicios_produccion():
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg_pool import ConnectionPool

    from gerald.agents.a2_boceto import InterpreteVision, OcrVision
    from gerald.db.postgres import AlmacenPG, PedidosPG, cargar_parametros
    from gerald.decision.decide import EvaluadorLLM
    from gerald.notificaciones import NotificadorCorreo

    cfg = settings()
    pool = ConnectionPool(
        cfg.database_url.get_secret_value(),
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=True,
    )
    servicios = Servicios(
        pedidos=PedidosPG(pool),
        almacen=AlmacenPG(pool),
        notificador=NotificadorCorreo(cfg.smtp_host),
        interprete=InterpreteVision(),
        evaluador=EvaluadorLLM(),
        parametros=cargar_parametros(pool),
        ocr=OcrVision(),
        correo_admin=cfg.correo_admin,
        correo_almacen=cfg.correo_almacen,
    )
    return construir_grafo(servicios, PostgresSaver(pool)), servicios


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    configurar_trazas()
    if settings().modo == "demo":
        from gerald.demo import construir_servicios_demo

        ESTADO["grafo"], ESTADO["servicios"] = construir_servicios_demo()
    else:
        ESTADO["grafo"], ESTADO["servicios"] = construir_servicios_produccion()
    yield


app = FastAPI(title="Gerald Sport · Pedidos", lifespan=ciclo_vida)


def _grafo():
    return ESTADO["grafo"], ESTADO["servicios"]


def _pausa(pedido_id: str, tipo: str):
    grafo, _ = _grafo()
    info = resumen(grafo, pedido_id)
    if not info["pausa"] or info["pausa"]["tipo"] != tipo:
        raise HTTPException(status.HTTP_409_CONFLICT, "El pedido no espera esta acción")
    return info


# ---------- Cliente ----------
@app.post("/pedidos", status_code=status.HTTP_202_ACCEPTED)
async def crear_pedido(
    tareas: BackgroundTasks,
    datos: str = Form(..., description="JSON de DatosPedido"),
    archivo: UploadFile = File(...),
    usuario: Usuario = Depends(limitar),
):
    if usuario.rol != "cliente":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No autorizado")
    try:
        cuerpo = DatosPedido.model_validate_json(datos)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.errors(include_url=False)) from exc
    contenido = await validar_archivo(archivo)

    pedido_id = f"P-{uuid.uuid4().hex[:10].upper()}"
    destino = Path(settings().dir_bocetos) / f"{pedido_id}{Path(archivo.filename or '').suffix[:5]}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)

    pedido = PedidoEntrada(
        pedido_id=pedido_id,
        cliente_id=usuario.id,
        correo_cliente=usuario.correo,
        boceto_uri=str(destino),
        boceto_sha256=hashlib.sha256(contenido).hexdigest(),
        lineas=cuerpo.lineas,
        notas=cuerpo.notas,
    )
    grafo, servicios = _grafo()
    tareas.add_task(ejecutar_pedido, grafo, pedido, servicios)
    return {"pedido_id": pedido_id, "estado": "recibido"}


@app.get("/pedidos/{pedido_id}")
def ver_pedido(pedido_id: str, usuario: Usuario = Depends(requerir_rol("cliente", "administrador"))):
    grafo, _ = _grafo()
    valores = grafo.get_state({"configurable": {"thread_id": pedido_id}}).values
    if not valores or (usuario.rol == "cliente" and valores["pedido"].cliente_id != usuario.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    return resumen(grafo, pedido_id)


class Aceptacion(BaseModel):
    acepta: bool


@app.post("/pedidos/{pedido_id}/aceptacion")
def aceptar(pedido_id: str, cuerpo: Aceptacion, usuario: Usuario = Depends(requerir_rol("cliente"))):
    grafo, servicios = _grafo()
    _pausa(pedido_id, "aceptacion_cliente")
    if grafo.get_state({"configurable": {"thread_id": pedido_id}}).values["pedido"].cliente_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    servicios.pedidos.auditar(usuario.id, "aceptacion", pedido_id, cuerpo.model_dump())
    return reanudar(grafo, pedido_id, cuerpo.model_dump(), servicios)


# ---------- Administrador (solo por excepción) ----------
class Revision(BaseModel):
    aprobado: bool
    comentario: str = ""


@app.get("/revision")
def bandeja(usuario: Usuario = Depends(requerir_rol("administrador"))):
    _, servicios = _grafo()
    return {"en_revision": servicios.pedidos.vencidos("en_revision", 0)}


@app.post("/revision/{pedido_id}")
def revisar(pedido_id: str, cuerpo: Revision, usuario: Usuario = Depends(requerir_rol("administrador"))):
    grafo, servicios = _grafo()
    _pausa(pedido_id, "revision_admin")
    servicios.pedidos.auditar(usuario.id, "revision", pedido_id, cuerpo.model_dump())
    try:
        return reanudar(grafo, pedido_id, cuerpo.model_dump(), servicios)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El rechazo requiere comentario") from exc


@app.get("/calibracion")
def ver_calibracion(dias: int = 7, usuario: Usuario = Depends(requerir_rol("administrador", "auditor"))):
    """Bucle de calibración: confianza vs resultado. Las sugerencias no cambian parámetros solas."""
    _, servicios = _grafo()
    return informe(servicios.pedidos.etiquetas(max(1, min(dias, 365))), servicios.parametros, dias)


# ---------- Almacén (solo cuando hay faltantes) ----------
class Ingreso(BaseModel):
    material_id: str
    cantidad: Decimal = Field(..., gt=0)


@app.post("/almacen/ingresos")
def registrar_ingreso(cuerpo: Ingreso, usuario: Usuario = Depends(requerir_rol("almacen"))):
    grafo, servicios = _grafo()
    pedidos = servicios.almacen.ingresar(cuerpo.material_id, cuerpo.cantidad)
    servicios.pedidos.auditar(usuario.id, "ingreso_material", "", cuerpo.model_dump(mode="json"))
    return {pid: reanudar(grafo, pid, None, servicios) for pid in pedidos}
