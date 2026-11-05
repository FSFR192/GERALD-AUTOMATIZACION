"""Notificador de producción (P08): correo con plantillas e idempotencia por (pedido, evento, destino)."""

import logging
import smtplib
import time
from email.message import EmailMessage
from typing import Any

from gerald.errores import ErrorTransitorio

log = logging.getLogger("gerald.notificaciones")

PLANTILLAS: dict[str, tuple[str, str]] = {
    "recepcion": ("Recibimos su pedido {pedido_id}", "Su pedido fue registrado y está en proceso."),
    "observaciones": (
        "Su pedido {pedido_id} requiere ajustes",
        "Para continuar, corrija lo siguiente:\n{observaciones}",
    ),
    "duplicado": ("Pedido ya registrado", "Este pedido ya existe como {pedido_id}."),
    "revision": (
        "Revisión requerida: {pedido_id}",
        "Motivo: {motivo}\nAprobar o rechazar en la bandeja.",
    ),
    "cotizacion": (
        "Cotización del pedido {pedido_id}",
        "Costo total: S/ {costo_total_pen}. Acepte con un clic desde el enlace.",
    ),
    "recordatorio": ("Recordatorio: pedido {pedido_id}", "Tiene una acción pendiente."),
    "abastecimiento": ("Abastecimiento requerido: {pedido_id}", "Faltantes: {faltantes}"),
    "confirmado": (
        "Pedido {pedido_id} confirmado",
        "Fecha estimada de entrega: {fecha_estimada}.\n{lista_materiales}",
    ),
    "alerta": ("ALERTA sistema: {pedido_id}", "Origen: {origen}\nError: {error}"),
    "calibracion": (
        "Alerta de deriva en la calibración",
        "Revise los umbrales de la política:\n{sugerencias}",
    ),
}


class NotificadorCorreo:
    """Un correo caído nunca detiene a los agentes (P08): el aviso queda en la bandeja de salida y la
    tarea programada lo reintenta. El portal web es el canal principal de las acciones del cliente."""

    PAUSA_TRAS_FALLO_S = 60  # no insistir con un servidor caído en cada aviso

    def __init__(self, host: str, remitente: str = "no-responder@geraldsport.pe") -> None:
        self.host = host
        self.remitente = remitente
        self._enviados: set[tuple[str, str, str]] = set()  # en producción: tabla con UNIQUE
        self.bandeja_salida: list[tuple[str, str, str, dict[str, Any]]] = []
        self._caido_hasta = 0.0

    def enviar(self, evento: str, destinatario: str, pedido_id: str, datos: dict[str, Any]) -> None:
        clave = (pedido_id, evento, destinatario)
        if clave in self._enviados and evento != "recordatorio":
            return
        try:
            self._enviar_smtp(evento, destinatario, pedido_id, datos)
        except ErrorTransitorio:
            log.warning("correo [%s] a %s en cola: servidor no disponible", evento, pedido_id)
            self.bandeja_salida.append((evento, destinatario, pedido_id, datos))
            return
        self._enviados.add(clave)

    def reintentar_pendientes(self) -> int:
        """Reenvía la bandeja de salida (tarea cada 15 min). Devuelve cuántos se enviaron."""
        pendientes, self.bandeja_salida, self._caido_hasta = self.bandeja_salida, [], 0.0
        enviados = 0
        for evento, destinatario, pedido_id, datos in pendientes:
            try:
                self._enviar_smtp(evento, destinatario, pedido_id, datos)
            except ErrorTransitorio:
                self.bandeja_salida.append((evento, destinatario, pedido_id, datos))
                continue
            self._enviados.add((pedido_id, evento, destinatario))
            enviados += 1
        return enviados

    def _enviar_smtp(self, evento: str, destinatario: str, pedido_id: str, datos: dict[str, Any]) -> None:
        if time.monotonic() < self._caido_hasta:
            raise ErrorTransitorio("notificacion", "servidor de correo no disponible")
        asunto, cuerpo = PLANTILLAS[evento]
        valores = {"pedido_id": pedido_id, **{k: _texto(v) for k, v in datos.items()}}
        msg = EmailMessage()
        msg["From"], msg["To"] = self.remitente, destinatario
        msg["Subject"] = asunto.format_map(_Seguro(valores))
        msg.set_content(cuerpo.format_map(_Seguro(valores)))
        try:
            with smtplib.SMTP(self.host, timeout=5) as smtp:
                smtp.send_message(msg)
        except (OSError, smtplib.SMTPException) as exc:
            self._caido_hasta = time.monotonic() + self.PAUSA_TRAS_FALLO_S
            raise ErrorTransitorio("notificacion", "servidor de correo no disponible") from exc


class _Seguro(dict):
    def __missing__(self, clave: str) -> str:
        return ""


def _texto(valor: Any) -> str:
    if isinstance(valor, list):
        return "\n".join(f"- {v}" for v in valor)
    return str(valor)
