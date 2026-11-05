"""Puerta de seguridad (P07): autenticación, autorización por rol, límite de tasa y validación de archivo."""

import io
import time
from collections import defaultdict, deque
from typing import Literal

import jwt
from fastapi import Depends, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from gerald.config import settings

Rol = Literal["cliente", "administrador", "almacen", "auditor"]

FIRMAS = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"%PDF-": "application/pdf",
}


class Usuario(BaseModel):
    id: str
    rol: Rol
    correo: str


# Declarado como esquema Bearer para que OpenAPI/Swagger muestre el botón "Authorize".
# auto_error=False: sin token respondemos 401 (no el 403 por defecto de FastAPI).
esquema_bearer = HTTPBearer(auto_error=False, description="JWT firmado (HS256) con sub, rol y correo")


def autenticar(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
) -> Usuario:
    if credenciales is None or credenciales.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado")
    try:
        datos = jwt.decode(
            credenciales.credentials, settings().jwt_secreto.get_secret_value(), algorithms=["HS256"]
        )
        return Usuario(id=datos["sub"], rol=datos["rol"], correo=datos["correo"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado") from exc


def requerir_rol(*roles: Rol):
    def dependencia(usuario: Usuario = Depends(autenticar)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No autorizado")
        return usuario

    return dependencia


class LimitadorTasa:
    """Ventana deslizante en memoria. En despliegue con varias réplicas, usar Redis."""

    def __init__(self, por_minuto: int) -> None:
        self.por_minuto = por_minuto
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def __call__(self, usuario: Usuario = Depends(autenticar)) -> Usuario:
        ahora, cola = time.monotonic(), self._hits[usuario.id]
        while cola and ahora - cola[0] > 60:
            cola.popleft()
        if len(cola) >= self.por_minuto:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiadas solicitudes")
        cola.append(ahora)
        return usuario


limitar = LimitadorTasa(settings().limite_por_minuto)


async def validar_archivo(archivo: UploadFile) -> bytes:
    """Tipo por firma (no por extensión), tamaño máximo y antivirus."""
    maximo = settings().tamano_max_mb * 1024 * 1024
    contenido = await archivo.read(maximo + 1)
    if len(contenido) > maximo:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Archivo demasiado grande")
    if not any(contenido.startswith(firma) for firma in FIRMAS):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Use JPG, PNG o PDF")
    escanear_antivirus(contenido)
    return contenido


def escanear_antivirus(contenido: bytes) -> None:
    """Punto de integración con ClamAV (clamd). Rechaza el archivo si se detecta amenaza."""
    try:
        import clamd  # opcional en desarrollo
    except ImportError:
        return
    resultado = clamd.ClamdNetworkSocket().instream(io.BytesIO(contenido))
    if resultado.get("stream", ("OK",))[0] != "OK":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Archivo rechazado por seguridad")
