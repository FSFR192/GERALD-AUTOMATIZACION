"""API REST de Gerald Sport. Puntos de contacto humanos: crear pedido, aceptar, revisar, abastecer."""

import hashlib
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response
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
        timeout=2.0,
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
    modo = os.environ.get("GERALD_MODO") or settings().modo
    if modo == "demo":
        from gerald.demo import construir_servicios_demo

        ESTADO["grafo"], ESTADO["servicios"] = construir_servicios_demo()
    else:
        try:
            ESTADO["grafo"], ESTADO["servicios"] = construir_servicios_produccion()
        except Exception:
            from gerald.demo import construir_servicios_demo

            ESTADO["grafo"], ESTADO["servicios"] = construir_servicios_demo()
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

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class VercelPathRewriteMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = dict(scope.get("headers", []))
            matched = headers.get(b"x-matched-path") or headers.get(b"x-forwarded-uri") or headers.get(b"x-invoke-path")
            if matched:
                matched_str = matched.decode("latin1").split("?")[0]
                curr_path = scope.get("path", "")
                if curr_path in ("/api/index.py", "/api/index", "/api") or curr_path.startswith("/api/index"):
                    scope["path"] = matched_str
        await self.app(scope, receive, send)


app.add_middleware(VercelPathRewriteMiddleware)


@app.get("/", include_in_schema=False)
@app.get("/app", include_in_schema=False)
@app.get("/app/", include_in_schema=False)
@app.get("/api", include_in_schema=False)
@app.get("/api/", include_in_schema=False)
@app.get("/api/index", include_in_schema=False)
@app.get("/api/index.py", include_in_schema=False)
def index_portal():
    archivo_index = DIR_WEB / "index.html"
    if archivo_index.is_file():
        return FileResponse(archivo_index, media_type="text/html")
    raiz_index = Path(__file__).resolve().parent.parent.parent / "public" / "index.html"
    if raiz_index.is_file():
        return FileResponse(raiz_index, media_type="text/html")
    return RedirectResponse(url="/docs")


@app.get("/app.js", include_in_schema=False)
@app.get("/app/app.js", include_in_schema=False)
def portal_js():
    archivo_js = DIR_WEB / "app.js"
    if archivo_js.is_file():
        return FileResponse(archivo_js, media_type="application/javascript")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "app.js no encontrado")


@app.get("/estilos.css", include_in_schema=False)
@app.get("/app/estilos.css", include_in_schema=False)
def portal_css():
    archivo_css = DIR_WEB / "estilos.css"
    if archivo_css.is_file():
        return FileResponse(archivo_css, media_type="text/css")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "estilos.css no encontrado")


@app.get("/informe", include_in_schema=False)
@app.get("/informe.html", include_in_schema=False)
def portal_informe():
    archivo_informe = Path(__file__).resolve().parent.parent.parent / "INFORME_LANGCHAIN_GERALD_SPORT.html"
    if archivo_informe.is_file():
        return FileResponse(archivo_informe, media_type="text/html")
    archivo_alt = DIR_WEB / "informe.html"
    if archivo_alt.is_file():
        return FileResponse(archivo_alt, media_type="text/html")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "informe.html no encontrado")


@app.get("/diagrama_arquitectura.jpg", include_in_schema=False)
@app.get("/images/diagrama_arquitectura.jpg", include_in_schema=False)
def img_diagrama_arq():
    raiz = Path(__file__).resolve().parent.parent.parent
    for p in (raiz / "diagrama_arquitectura.jpg", DIR_WEB / "diagrama_arquitectura.jpg", raiz / "public" / "diagrama_arquitectura.jpg"):
        if p.is_file():
            return FileResponse(p, media_type="image/jpeg")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrada")


@app.get("/diagrama_bpmn.jpg", include_in_schema=False)
@app.get("/images/diagrama_bpmn.jpg", include_in_schema=False)
def img_diagrama_bpmn():
    raiz = Path(__file__).resolve().parent.parent.parent
    for p in (raiz / "diagrama_bpmn.jpg", DIR_WEB / "diagrama_bpmn.jpg", raiz / "public" / "diagrama_bpmn.jpg"):
        if p.is_file():
            return FileResponse(p, media_type="image/jpeg")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrada")


@app.get("/captura_langsmith_dashboard.png", include_in_schema=False)
@app.get("/images/captura_langsmith_dashboard.png", include_in_schema=False)
def img_ls_dash():
    raiz = Path(__file__).resolve().parent.parent.parent
    for p in (raiz / "captura_langsmith_dashboard.png", DIR_WEB / "captura_langsmith_dashboard.png", raiz / "public" / "captura_langsmith_dashboard.png"):
        if p.is_file():
            return FileResponse(p, media_type="image/png")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrada")


@app.get("/captura_langsmith_trace.jpg", include_in_schema=False)
@app.get("/images/captura_langsmith_trace.jpg", include_in_schema=False)
def img_ls_trace():
    raiz = Path(__file__).resolve().parent.parent.parent
    for p in (raiz / "captura_langsmith_trace.jpg", DIR_WEB / "captura_langsmith_trace.jpg", raiz / "public" / "captura_langsmith_trace.jpg"):
        if p.is_file():
            return FileResponse(p, media_type="image/jpeg")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrada")


def _grafo():
    configurar_trazas()
    if "grafo" not in ESTADO or "servicios" not in ESTADO:
        if settings().modo == "demo":
            from gerald.demo import construir_servicios_demo

            ESTADO["grafo"], ESTADO["servicios"] = construir_servicios_demo()
        else:
            ESTADO["grafo"], ESTADO["servicios"] = construir_servicios_produccion()
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
    if not valores:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    pedido = valores.get("pedido")
    if (
        usuario.rol == "cliente"
        and pedido
        and pedido.cliente_id != usuario.id
        and getattr(pedido, "correo_cliente", None) != usuario.correo
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No autorizado para ver este pedido")
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
@app.post("/api/pedidos", status_code=status.HTTP_202_ACCEPTED, include_in_schema=False)
async def crear_pedido(
    tareas: BackgroundTasks,
    datos: str = Form(None, description="JSON con las líneas del pedido"),
    lineas: str = Form(None, description="JSON alternativo de líneas"),
    notas: str = Form(None, description="Notas"),
    cliente_id: str = Form(None, description="Cliente corporativo destino"),
    archivo: UploadFile = File(None, description="Boceto JPG, PNG o PDF (máx. 10 MB)"),
    boceto: UploadFile = File(None, description="Alias para archivo de boceto"),
    usuario: Usuario = Depends(limitar),
):
    if usuario.rol not in ("cliente", "administrador", "almacen", "auditor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No autorizado")

    archivo_final = archivo or boceto
    if archivo_final is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Se requiere adjuntar un archivo o boceto")

    if datos:
        try:
            cuerpo = DatosPedido.model_validate_json(datos)
        except ValidationError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.errors(include_url=False)) from exc
    elif lineas:
        import json

        try:
            lineas_lista = json.loads(lineas)
            cuerpo = DatosPedido(lineas=lineas_lista, notas=notas, cliente_id=cliente_id)
        except Exception as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Error en líneas del pedido: {exc}") from exc
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Se requieren los datos o líneas del pedido")

    contenido = await validar_archivo(archivo_final)

    pedido_id = f"P-{uuid.uuid4().hex[:10].upper()}"
    try:
        destino = Path(settings().dir_bocetos) / f"{pedido_id}{Path(archivo_final.filename or '').suffix[:5]}"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
    except OSError:
        destino = Path("/tmp/bocetos") / f"{pedido_id}{Path(archivo_final.filename or '').suffix[:5]}"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)

    # Asignar cliente destino: usa el cliente especificado en payload o usuario.id
    cid = getattr(cuerpo, "cliente_id", None) or cliente_id or usuario.id

    pedido = PedidoEntrada(
        pedido_id=pedido_id,
        cliente_id=cid,
        correo_cliente=usuario.correo,
        boceto_uri=str(destino),
        boceto_sha256=hashlib.sha256(contenido).hexdigest(),
        lineas=cuerpo.lineas,
        notas=cuerpo.notas,
    )
    grafo, servicios = _grafo()
    tareas.add_task(ejecutar_pedido, grafo, pedido, servicios)
    return {"pedido_id": pedido_id, "estado": "recibido", "cliente_id": cid}


@app.get(
    "/pedidos/{pedido_id}",
    tags=["Cliente"],
    summary="Consultar estado del pedido",
    description="Estado, acción pendiente (`pausa`) y observaciones.",
)
@app.get("/api/pedidos/{pedido_id}", tags=["Cliente"], include_in_schema=False)
def ver_pedido(pedido_id: str, usuario: Usuario = Depends(requerir_rol("cliente", "administrador", "almacen", "auditor"))):
    _pedido_visible(pedido_id, usuario)
    return _detalle(pedido_id, con_materiales=usuario.rol in ("administrador", "almacen", "auditor"))


@app.get("/pedidos", tags=["Cliente"], summary="Mis pedidos")
@app.get("/api/pedidos", tags=["Cliente"], include_in_schema=False)
def mis_pedidos(usuario: Usuario = Depends(requerir_rol("cliente", "administrador", "almacen", "auditor"))):
    _, servicios = _grafo()
    if usuario.rol in ("administrador", "almacen", "auditor"):
        ids = [pid for pid in servicios.pedidos.todos() if _valores(pid)]
    else:
        ids = [
            pid for pid in servicios.pedidos.todos()
            if _valores(pid) and (
                _valores(pid)["pedido"].cliente_id == usuario.id
                or getattr(_valores(pid)["pedido"], "correo_cliente", None) == usuario.correo
            )
        ]
    return {"pedidos": [_detalle(pid, con_materiales=usuario.rol in ("administrador", "almacen", "auditor")) for pid in ids]}


def _generar_png_boceto(pedido) -> bytes:
    """Genera un boceto PNG técnico nítido con especificaciones si el archivo en Vercel /tmp expiró."""
    from PIL import Image, ImageDraw
    import io

    ancho, alto = 500, 500
    img = Image.new("RGB", (ancho, alto), color=(15, 23, 42))
    d = ImageDraw.Draw(img)

    # Marco técnico
    d.rectangle([10, 10, ancho - 10, alto - 10], outline=(59, 130, 246), width=2)
    d.rectangle([14, 14, ancho - 14, alto - 14], outline=(30, 41, 59), width=1)

    # Cabecera técnica
    d.rectangle([15, 15, ancho - 15, 60], fill=(30, 41, 59))
    d.text((25, 22), "GERALD SPORT · FICHA TÉCNICA IA", fill=(255, 255, 255))
    d.text((25, 38), "SISTEMA DE DISEÑO MULTIMODAL & TRAZABILIDAD TEXTIL", fill=(148, 163, 184))

    cid = getattr(pedido, "cliente_id", "CORP")
    colores_map = {
        "C-ENTEL-PE": ((0, 85, 184), (255, 106, 19), "ENTEL PERÚ"),
        "C-BANCO-BCP": ((0, 36, 106), (255, 120, 0), "BANCO BCP"),
        "C-INTERBANK": ((5, 150, 105), (16, 185, 129), "INTERBANK"),
        "C-CLARO-PE": ((218, 41, 28), (255, 255, 255), "CLARO PERÚ"),
    }
    color_prim, color_sec, nombre_emp = colores_map.get(cid, ((79, 70, 229), (232, 85, 43), cid))

    # Cuerpo de camiseta deportiva
    d.polygon(
        [(180, 110), (320, 110), (380, 170), (340, 210), (310, 180), (310, 380), (190, 380), (190, 180), (160, 210), (120, 170)],
        fill=color_prim,
        outline=(255, 255, 255),
    )
    # Mangas
    d.polygon([(180, 110), (120, 170), (160, 210), (190, 180)], fill=color_sec)
    d.polygon([(320, 110), (380, 170), (340, 210), (310, 180)], fill=color_sec)
    # Cuello
    d.arc([220, 95, 280, 140], start=0, end=180, fill=(255, 255, 255), width=4)

    # Logo / Texto en pecho
    d.rectangle([215, 220, 285, 250], fill=(255, 255, 255), outline=(255, 255, 255))
    d.text((225, 228), nombre_emp[:10], fill=(15, 23, 42))

    # Detalle de líneas pedidas
    lineas = getattr(pedido, "lineas", [])
    txt_lineas = ", ".join(f"{l.cantidad} {l.prenda} {l.talla}" for l in lineas[:2]) if lineas else "Prenda deportiva corporativa"
    d.text((25, 405), f"LÍNEA: {txt_lineas[:45]}", fill=(226, 232, 240))
    d.text((25, 425), f"CLIENTE: {nombre_emp} · TENANT: {cid}", fill=(148, 163, 184))
    d.text((25, 445), f"HASH: {getattr(pedido, 'boceto_sha256', 'VALIDADO')[:20]}...", fill=(99, 102, 241))
    d.text((25, 465), "TECNOLOGÍA: Dry-Fit 180g / Sublimado Digital / Costura Reforzada", fill=(100, 116, 139))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@app.get("/pedidos/{pedido_id}/boceto", tags=["Cliente"], summary="Ver el boceto del pedido")
@app.get("/api/pedidos/{pedido_id}/boceto", tags=["Cliente"], include_in_schema=False)
def ver_boceto(pedido_id: str, usuario: Usuario = Depends(requerir_rol("cliente", "administrador", "almacen", "auditor"))):
    pedido_vis = _pedido_visible(pedido_id, usuario)
    pedido_item = pedido_vis["pedido"]
    ruta_str = getattr(pedido_item, "boceto_uri", "")
    if ruta_str:
        ruta = Path(ruta_str)
        if ruta.is_file():
            with ruta.open("rb") as f:
                cabecera = f.read(8)
            tipo = next((m for firma, m in FIRMAS.items() if cabecera.startswith(firma)), None)
            if tipo:
                return FileResponse(ruta, media_type=tipo, headers={"X-Content-Type-Options": "nosniff"})
    png_bytes = _generar_png_boceto(pedido_item)
    return Response(content=png_bytes, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/catalogo", tags=["Cliente"], summary="Prendas y tallas disponibles")
@app.get("/api/catalogo", tags=["Cliente"], include_in_schema=False)
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
@app.post("/api/pedidos/{pedido_id}/aceptacion", tags=["Cliente"], include_in_schema=False)
def aceptar(pedido_id: str, cuerpo: Aceptacion, usuario: Usuario = Depends(requerir_rol("cliente", "administrador", "almacen", "auditor"))):
    grafo, servicios = _grafo()
    _pausa(pedido_id, "aceptacion_cliente")
    pedido_vals = grafo.get_state({"configurable": {"thread_id": pedido_id}}).values.get("pedido")
    if not pedido_vals:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    if (
        usuario.rol == "cliente"
        and pedido_vals.cliente_id != usuario.id
        and getattr(pedido_vals, "correo_cliente", None) != usuario.correo
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No autorizado")
    servicios.pedidos.auditar(usuario.id, "aceptacion", pedido_id, cuerpo.model_dump())
    return reanudar(grafo, pedido_id, cuerpo.model_dump(), servicios)


# ---------- Administrador (solo por excepción) ----------
class Revision(BaseModel):
    aprobado: bool
    comentario: str = ""


@app.get("/revision", tags=["Administrador"], summary="Bandeja de pedidos en revisión")
def bandeja(usuario: Usuario = Depends(requerir_rol("administrador", "auditor"))):
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
def revisar(pedido_id: str, cuerpo: Revision, usuario: Usuario = Depends(requerir_rol("administrador", "auditor"))):
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
def requerimientos(usuario: Usuario = Depends(requerir_rol("almacen", "administrador"))):
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
def registrar_ingreso(cuerpo: Ingreso, usuario: Usuario = Depends(requerir_rol("almacen", "administrador"))):
    grafo, servicios = _grafo()
    pedidos = servicios.almacen.ingresar(cuerpo.material_id, cuerpo.cantidad)
    servicios.pedidos.auditar(usuario.id, "ingreso_material", "", cuerpo.model_dump(mode="json"))
    return {pid: reanudar(grafo, pid, None, servicios) for pid in pedidos}


# ---------- Modo demo: inicio de sesión sin pegar tokens ----------
class SesionDemo(BaseModel):
    rol: Rol
    id: str = Field(..., pattern=r"^[A-Za-z0-9-]{2,20}$")


@app.post("/demo/sesion", include_in_schema=False)
@app.post("/demo/sesion/", include_in_schema=False)
@app.post("/api/demo/sesion", include_in_schema=False)
@app.post("/api/demo/sesion/", include_in_schema=False)
def sesion_demo(cuerpo: SesionDemo):
    """Solo con GERALD_MODO=demo. En producción el token lo emite el proveedor de identidad."""
    if settings().modo != "demo":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No disponible")
    from gerald.demo import token

    return {"token": token(cuerpo.rol, cuerpo.id), "rol": cuerpo.rol, "id": cuerpo.id}


@app.get("/demo/estado", include_in_schema=False)
@app.get("/demo/estado/", include_in_schema=False)
@app.get("/api/demo/estado", include_in_schema=False)
@app.get("/api/demo/estado/", include_in_schema=False)
def estado_demo():
    return {"demo": settings().modo == "demo"}


@app.post("/demo/simular", include_in_schema=False)
@app.post("/demo/simular/", include_in_schema=False)
@app.post("/api/demo/simular", include_in_schema=False)
@app.post("/api/demo/simular/", include_in_schema=False)
def simular_pedidos(usuario: Usuario = Depends(autenticar)):
    """Puebla el sistema con pedidos simulados multiempresa para demostrar la suite."""
    if settings().modo != "demo":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Solo en modo demo")
    
    import time
    grafo, servicios = _grafo()
    from gerald.schemas.pedido import LineaPedido
    from pathlib import Path
    
    try:
        dir_bocetos = Path(settings().dir_bocetos)
        dir_bocetos.mkdir(parents=True, exist_ok=True)
    except OSError:
        dir_bocetos = Path("/tmp/bocetos")
        dir_bocetos.mkdir(parents=True, exist_ok=True)
    
    ts = int(time.time() * 10) % 100000
    
    casos = [
        {
            "pedido_id": f"P-ENTEL-{ts:05d}",
            "cliente_id": "C-ENTEL-PE",
            "empresa": "Entel Perú S.A.",
            "correo": "compras@entel.pe",
            "lineas": [LineaPedido(prenda="polo", talla="L", color=f"azul entel #{ts%9+1}", cantidad=45)],
            "notas": "Uniformes corporativos sucursal Lima Centro. Bordado pecho izq.",
        },
        {
            "pedido_id": f"P-BCP-{ts+1:05d}",
            "cliente_id": "C-BANCO-BCP",
            "empresa": "Banco de Crédito BCP",
            "correo": "logistica@bcp.com.pe",
            "lineas": [LineaPedido(prenda="casaca", talla="M", color=f"azul noche #{ts%9+1}", cantidad=25)],
            "notas": "Casacas térmicas para evento anual de innovación BCP.",
        },
        {
            "pedido_id": f"P-INTER-{ts+2:05d}",
            "cliente_id": "C-INTERBANK",
            "empresa": "Interbank",
            "correo": "talento@interbank.pe",
            "lineas": [LineaPedido(prenda="short", talla="M", color=f"verde corporativo #{ts%9+1}", cantidad=30)],
            "notas": "Torneo deportivo interbancario corporativo.",
        },
        {
            "pedido_id": f"P-CLARO-{ts+3:05d}",
            "cliente_id": "C-CLARO-PE",
            "empresa": "Claro Perú",
            "correo": "eventos@claro.com.pe",
            "lineas": [LineaPedido(prenda="polo", talla="S", color=f"rojo claro #{ts%9+1}", cantidad=60)],
            "notas": "Maratón Claro 10K. Sublimación logo institucional.",
        },
    ]
    
    creados = []
    for i, c in enumerate(casos):
        boceto_archivo = dir_bocetos / f"boceto_{c['pedido_id']}.png"
        # PNG 1x1 con bytes variables para firma sha256 única por pedido
        pixel_byte = (ts + i) % 255
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            + bytes([pixel_byte])
        )
        boceto_archivo.write_bytes(png_bytes)
        sha_boceto = hashlib.sha256(png_bytes).hexdigest()
        
        p = PedidoEntrada(
            pedido_id=c["pedido_id"],
            cliente_id=c["cliente_id"],
            correo_cliente=c["correo"],
            boceto_uri=str(boceto_archivo),
            boceto_sha256=sha_boceto,
            lineas=c["lineas"],
            notas=c["notas"],
        )
        res = ejecutar_pedido(grafo, p, servicios)
        creados.append({
            "pedido_id": c["pedido_id"],
            "cliente_id": c["cliente_id"],
            "empresa": c["empresa"],
            "estado": res.get("estado")
        })
        
    return {"status": "ok", "total": len(creados), "pedidos_simulados": creados}


# ---------- Portal web (interfaz de usuario) ----------
app.mount("/app", StaticFiles(directory=DIR_WEB, html=True), name="portal")
