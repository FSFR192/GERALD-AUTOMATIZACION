"""API REST de Gerald Sport. Puntos de contacto humanos: crear pedido, aceptar, revisar, abastecer."""

import hashlib
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from gerald.api.seguridad import FIRMAS, Rol, Usuario, autenticar, limitar, requerir_rol, validar_archivo
from gerald.calibracion import informe
from gerald.config import settings
from gerald.graph import construir_grafo, ejecutar_pedido, reanudar, resumen, serializador
from gerald.observabilidad import configurar_trazas
from gerald.schemas.pedido import DatosPedido, PedidoEntrada
from gerald.servicios import Servicios
from gerald.traza import traza

ESTADO: dict = {}
DIR_WEB = Path(__file__).resolve().parent.parent / "web"


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
    return construir_grafo(servicios, PostgresSaver(pool, serde=serializador())), servicios


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    configurar_trazas()
    if settings().modo == "demo":
        from gerald.demo import construir_servicios_demo

        ESTADO["grafo"], ESTADO["servicios"] = construir_servicios_demo()
    else:
        ESTADO["grafo"], ESTADO["servicios"] = construir_servicios_produccion()
    yield


DESCRIPCION = """
Contratación de pedidos y coordinación de materiales (BPMN TO-BE). Cada grupo es un carril del BPMN:
el cliente envía y acepta con 1 clic, el administrador solo revisa excepciones y el almacén solo
interviene cuando faltan materiales.

**Cómo probar:** pulse **Authorize** y pegue un token JWT. En modo demo se generan con
`uv run python -m gerald.demo <rol> <id>` (roles: `cliente`, `administrador`, `almacen`, `auditor`).
"""

ETIQUETAS = [
    {"name": "Cliente", "description": "Enviar el pedido, consultar su estado y aceptar la cotización."},
    {"name": "Administrador", "description": "Revisión por excepción: confianza no alta o costo > umbral."},
    {"name": "Almacén", "description": "Registrar el ingreso de material faltante; reanuda los pedidos."},
    {"name": "Gobernanza", "description": "Bucle de calibración: confianza vs resultado real."},
]

app = FastAPI(
    title="Gerald Sport · Pedidos",
    version="0.1.0",
    description=DESCRIPCION,
    openapi_tags=ETIQUETAS,
    lifespan=ciclo_vida,
)


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/app/")


def _grafo():
    return ESTADO["grafo"], ESTADO["servicios"]


def _valores(pedido_id: str) -> dict:
    grafo, _ = _grafo()
    return grafo.get_state({"configurable": {"thread_id": pedido_id}}).values


ESTADOS_DE_ERROR = {
    "detenido": "Detenido por un error del sistema; se alertó al responsable.",
    "pendiente_reproceso": "Servicio no disponible; se reintentará automáticamente.",
}


def _detalle(pedido_id: str, con_materiales: bool) -> dict:
    """Resumen para la interfaz. Los precios unitarios del almacén solo los ve el administrador."""
    grafo, servicios = _grafo()
    valores = _valores(pedido_id)
    pedido, calculo = valores["pedido"], valores.get("calculo")
    detalle = {
        "pedido_id": pedido_id,
        **resumen(grafo, pedido_id),
        "cliente_id": pedido.cliente_id,
        "lineas": [linea.model_dump() for linea in pedido.lineas],
        "notas": pedido.notas,
        "costo_total_pen": str(calculo.costo_total_pen) if calculo and calculo.lineas else None,
        "actividad": traza(grafo, pedido_id, detallado=con_materiales),
    }
    registrado = servicios.pedidos.estado_de(pedido_id)
    if registrado in ESTADOS_DE_ERROR:  # el grafo quedó a mitad de camino: mostrar la verdad
        detalle["estado"] = registrado
        for paso in detalle["actividad"]:
            if paso["estado"] == "esperando":
                paso["estado"], paso["detalle"] = "error", ESTADOS_DE_ERROR[registrado]
    if con_materiales and calculo:
        detalle["materiales"] = [linea.model_dump(mode="json") for linea in calculo.lineas]
        veredicto = valores.get("veredicto")
        detalle["motivo"] = veredicto.motivo if veredicto else None
    return detalle


def _pedido_visible(pedido_id: str, usuario: Usuario) -> dict:
    valores = _valores(pedido_id)
    if not valores or (usuario.rol == "cliente" and valores["pedido"].cliente_id != usuario.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    return valores


def _pausa(pedido_id: str, tipo: str):
    grafo, _ = _grafo()
    info = resumen(grafo, pedido_id)
    if not info["pausa"] or info["pausa"]["tipo"] != tipo:
        raise HTTPException(status.HTTP_409_CONFLICT, "El pedido no espera esta acción")
    return info


# ---------- Cliente ----------
EJEMPLO_DATOS = '{"lineas": [{"prenda": "polo", "talla": "M", "color": "azul", "cantidad": 10}]}'


@app.post(
    "/pedidos",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Cliente"],
    summary="Enviar pedido con boceto, tallas, colores y cantidad",
    description="Inicia el flujo multiagente. Prendas del catálogo: polo (XS–XXL), short y casaca "
    "(S–XL). Para corregir un pedido observado, envíelo de nuevo con los cambios.",
)
async def crear_pedido(
    tareas: BackgroundTasks,
    datos: str = Form(..., description="JSON con las líneas del pedido", examples=[EJEMPLO_DATOS]),
    archivo: UploadFile = File(..., description="Boceto JPG, PNG o PDF (máx. 10 MB)"),
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


@app.get(
    "/pedidos/{pedido_id}",
    tags=["Cliente"],
    summary="Consultar estado del pedido",
    description="Estado, acción pendiente (`pausa`) y observaciones. El cliente solo ve sus pedidos.",
)
def ver_pedido(pedido_id: str, usuario: Usuario = Depends(requerir_rol("cliente", "administrador"))):
    _pedido_visible(pedido_id, usuario)
    return _detalle(pedido_id, con_materiales=usuario.rol == "administrador")


@app.get("/pedidos", tags=["Cliente"], summary="Mis pedidos")
def mis_pedidos(usuario: Usuario = Depends(requerir_rol("cliente"))):
    _, servicios = _grafo()
    ids = [pid for pid in servicios.pedidos.de_cliente(usuario.id) if _valores(pid)]
    return {"pedidos": [_detalle(pid, con_materiales=False) for pid in ids]}


@app.get("/pedidos/{pedido_id}/boceto", tags=["Cliente"], summary="Ver el boceto del pedido")
def ver_boceto(pedido_id: str, usuario: Usuario = Depends(requerir_rol("cliente", "administrador"))):
    ruta = Path(_pedido_visible(pedido_id, usuario)["pedido"].boceto_uri)
    if not ruta.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Boceto no disponible")
    with ruta.open("rb") as f:
        cabecera = f.read(8)
    tipo = next((m for firma, m in FIRMAS.items() if cabecera.startswith(firma)), None)
    if tipo is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Formato no soportado")
    return FileResponse(ruta, media_type=tipo, headers={"X-Content-Type-Options": "nosniff"})


@app.get("/catalogo", tags=["Cliente"], summary="Prendas y tallas disponibles")
def catalogo(usuario: Usuario = Depends(autenticar)):
    _, servicios = _grafo()
    return {"prendas": servicios.almacen.prendas()}


class Aceptacion(BaseModel):
    acepta: bool


@app.post(
    "/pedidos/{pedido_id}/aceptacion",
    tags=["Cliente"],
    summary="Aceptar cotización y contrato (1 clic)",
    description="`acepta: true` registra el contrato y reserva materiales; `false` cierra el pedido.",
)
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


@app.get("/revision", tags=["Administrador"], summary="Bandeja de pedidos en revisión")
def bandeja(usuario: Usuario = Depends(requerir_rol("administrador"))):
    _, servicios = _grafo()
    ids = [pid for pid in servicios.pedidos.vencidos("en_revision", 0) if _valores(pid)]
    return {"en_revision": ids, "pedidos": [_detalle(pid, con_materiales=True) for pid in ids]}


@app.post(
    "/revision/{pedido_id}",
    tags=["Administrador"],
    summary="Revisar y aprobar propuesta (solo excepciones)",
    description="Aprobar envía la cotización al cliente. Rechazar exige `comentario`, que se envía "
    "al cliente como observación.",
)
def revisar(pedido_id: str, cuerpo: Revision, usuario: Usuario = Depends(requerir_rol("administrador"))):
    grafo, servicios = _grafo()
    _pausa(pedido_id, "revision_admin")
    servicios.pedidos.auditar(usuario.id, "revision", pedido_id, cuerpo.model_dump())
    try:
        return reanudar(grafo, pedido_id, cuerpo.model_dump(), servicios)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El rechazo requiere comentario") from exc


@app.get("/calibracion", tags=["Gobernanza"], summary="Informe de calibración (confianza vs resultado)")
def ver_calibracion(dias: int = 7, usuario: Usuario = Depends(requerir_rol("administrador", "auditor"))):
    """Bucle de calibración: confianza vs resultado. Las sugerencias no cambian parámetros solas."""
    _, servicios = _grafo()
    return informe(servicios.pedidos.etiquetas(max(1, min(dias, 365))), servicios.parametros, dias)


# ---------- Almacén (solo cuando hay faltantes) ----------
class Ingreso(BaseModel):
    material_id: str
    cantidad: Decimal = Field(..., gt=0)


@app.get("/almacen/requerimientos", tags=["Almacén"], summary="Faltantes pendientes de abastecer")
def requerimientos(usuario: Usuario = Depends(requerir_rol("almacen"))):
    _, servicios = _grafo()
    pendientes = servicios.almacen.requerimientos_pendientes()
    stock = servicios.almacen.stock(sorted({r["material_id"] for r in pendientes}))
    nombres = servicios.almacen.materiales(list(stock))
    return {
        "requerimientos": [
            {
                **r,
                "faltante": str(r["faltante"]),
                "nombre": nombres[r["material_id"]].nombre if r["material_id"] in nombres else "",
                "unidad": nombres[r["material_id"]].unidad if r["material_id"] in nombres else "",
                "stock": str(stock.get(r["material_id"], 0)),
            }
            for r in pendientes
        ]
    }


@app.post(
    "/almacen/ingresos",
    tags=["Almacén"],
    summary="Abastecer material faltante",
    description="Suma stock y reanuda los pedidos que esperaban ese material.",
)
def registrar_ingreso(cuerpo: Ingreso, usuario: Usuario = Depends(requerir_rol("almacen"))):
    grafo, servicios = _grafo()
    pedidos = servicios.almacen.ingresar(cuerpo.material_id, cuerpo.cantidad)
    servicios.pedidos.auditar(usuario.id, "ingreso_material", "", cuerpo.model_dump(mode="json"))
    return {pid: reanudar(grafo, pid, None, servicios) for pid in pedidos}


# ---------- Modo demo: inicio de sesión sin pegar tokens ----------
class SesionDemo(BaseModel):
    rol: Rol
    id: str = Field(..., pattern=r"^[A-Za-z0-9-]{2,20}$")


@app.post("/demo/sesion", include_in_schema=False)
def sesion_demo(cuerpo: SesionDemo):
    """Solo con GERALD_MODO=demo. En producción el token lo emite el proveedor de identidad."""
    if settings().modo != "demo":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No disponible")
    from gerald.demo import token

    return {"token": token(cuerpo.rol, cuerpo.id), "rol": cuerpo.rol, "id": cuerpo.id}


@app.get("/demo/estado", include_in_schema=False)
def estado_demo():
    return {"demo": settings().modo == "demo"}


# ---------- Portal web (interfaz de usuario) ----------
app.mount("/app", StaticFiles(directory=DIR_WEB, html=True), name="portal")
