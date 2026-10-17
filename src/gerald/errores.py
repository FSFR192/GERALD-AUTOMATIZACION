"""Jerarquía de errores por clase (P05). Toda excepción técnica se traduce a una de estas."""


class ErrorGerald(Exception):
    def __init__(self, origen: str, mensaje: str) -> None:
        super().__init__(f"[{origen}] {mensaje}")
        self.origen = origen
        self.mensaje = mensaje


class ErrorDatos(ErrorGerald):
    """Datos del cliente inválidos o incompletos → observaciones. No se reintenta."""


class Duplicado(ErrorGerald):
    """El pedido ya fue registrado (misma clave SHA-256). No es una falla."""


class ErrorTransitorio(ErrorGerald):
    """Falla temporal (timeout, 429, 503, servicio no disponible) → RetryPolicy y cola de pendientes."""


class ErrorSistema(ErrorGerald):
    """Falla grave (cuota agotada, credencial revocada, error al registrar/reservar) → detener y alertar."""
