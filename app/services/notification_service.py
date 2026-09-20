from __future__ import annotations

import re
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.core.security import AuthContext
from app.repositories.notifications_repository import NotificationsRepository
from app.repositories.smtp_config_repository import SmtpConfigRepository
from app.repositories.email_template_repository import EmailTemplateRepository


class NotificationService:
    def __init__(
        self,
        notifications_repo: Optional[NotificationsRepository] = None,
        smtp_repo: Optional[SmtpConfigRepository] = None,
        templates_repo: Optional[EmailTemplateRepository] = None,
    ) -> None:
        self.notifications_repo = notifications_repo or NotificationsRepository()
        self.smtp_repo = smtp_repo or SmtpConfigRepository()
        self.templates_repo = templates_repo or EmailTemplateRepository()

    def _institution_id(self, auth: Optional[AuthContext]) -> Optional[int]:
        if auth is not None and not auth.is_platform_admin:
            return auth.institucion_id
        return None

    def _get_smtp_config(self, institucion_id: Optional[int]) -> Optional[dict]:
        return self.smtp_repo.get_config(institucion_id) or self.smtp_repo.get_config(None)

    def get_smtp_config(self, auth: Optional[AuthContext] = None) -> Optional[dict]:
        return self._get_smtp_config(self._institution_id(auth))

    def update_smtp_config(self, auth: AuthContext, payload) -> dict:
        inst = self._institution_id(auth)
        if inst is None:
            raise PermissionError("Institution membership required to configure SMTP")
        password = getattr(payload, "password", None)
        return self.smtp_repo.upsert(
            inst,
            servidor=payload.servidor,
            puerto=payload.puerto,
            cifrado=payload.cifrado,
            usuario=payload.usuario,
            password_secret_ref=password,
            correo_remitente=payload.correo_remitente,
            nombre_remitente=payload.nombre_remitente,
            timeout_segundos=payload.timeout_segundos,
            activo=payload.activo,
        )

    def list_notifications(self, auth: AuthContext) -> list[dict]:
        inst = self._institution_id(auth)
        if inst is None:
            return []
        return self.notifications_repo.list_by_institution(inst)

    def render_template(self, template: dict, data: dict) -> tuple[str, str]:
        def _fill(value: str) -> str:
            return re.sub(r"{{\s*([a-zA-Z0-9_]+)\s*}}", lambda m: str(data.get(m.group(1), m.group(0))), value or "")

        asunto = _fill(template.get("asunto") or "")
        contenido = _fill(template.get("contenido_html") or template.get("contenido_texto") or "")
        return asunto, contenido

    def _resolve_password(self, config: dict) -> Optional[str]:
        return (config.get("password_secret_ref") or "") or settings.smtp_password

    def _send_smtp(self, config: dict, to: str, subject: str, html: Optional[str], text: Optional[str]) -> None:
        password = self._resolve_password(config)
        servidor = config["servidor"]
        puerto = int(config.get("puerto") or 587)
        cifrado = (config.get("cifrado") or "STARTTLS").upper()
        timeout = int(config.get("timeout_segundos") or 30)
        remitente = config["correo_remitente"]
        nombre = config.get("nombre_remitente")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{nombre} <{remitente}>" if nombre else remitente
        msg["To"] = to
        msg.set_content(text or "")
        if html:
            msg.add_alternative(html, subtype="html")

        if cifrado == "SSL":
            server = smtplib.SMTP_SSL(servidor, puerto, timeout=timeout)
        else:
            server = smtplib.SMTP(servidor, puerto, timeout=timeout)
            if cifrado in ("STARTTLS", "TLS"):
                server.starttls()
        try:
            usuario = config.get("usuario")
            if usuario and password:
                server.login(usuario, password)
            server.send_message(msg)
        finally:
            server.quit()

    def send_email(
        self,
        auth: AuthContext,
        *,
        destinatario: str,
        asunto: str,
        contenido: str,
        contenido_texto: Optional[str] = None,
        tipo: str = "SYSTEM",
        suscripcion_id: Optional[int] = None,
        clave_idempotencia: Optional[str] = None,
    ) -> dict:
        return self._send_email(
            self._institution_id(auth),
            destinatario=destinatario,
            asunto=asunto,
            contenido=contenido,
            contenido_texto=contenido_texto,
            tipo=tipo,
            suscripcion_id=suscripcion_id,
            clave_idempotencia=clave_idempotencia,
        )

    def send_automated(
        self,
        institucion_id: Optional[int],
        *,
        destinatario: str,
        asunto: str,
        contenido: str,
        contenido_texto: Optional[str] = None,
        tipo: str = "SYSTEM",
        suscripcion_id: Optional[int] = None,
        clave_idempotencia: Optional[str] = None,
    ) -> dict:
        """Envío sin auth (p. ej. desde webhook Stripe)."""
        return self._send_email(
            institucion_id,
            destinatario=destinatario,
            asunto=asunto,
            contenido=contenido,
            contenido_texto=contenido_texto,
            tipo=tipo,
            suscripcion_id=suscripcion_id,
            clave_idempotencia=clave_idempotencia,
        )

    def _send_email(
        self,
        institucion_id: Optional[int],
        *,
        destinatario: str,
        asunto: str,
        contenido: str,
        contenido_texto: Optional[str] = None,
        tipo: str = "SYSTEM",
        suscripcion_id: Optional[int] = None,
        clave_idempotencia: Optional[str] = None,
    ) -> dict:
        if clave_idempotencia:
            existing = self.notifications_repo.get_by_idempotency(clave_idempotencia)
            if existing:
                return existing

        config = self._get_smtp_config(institucion_id)
        notification = self.notifications_repo.create(
            {
                "institucion_id": institucion_id,
                "suscripcion_id": suscripcion_id,
                "tipo": tipo,
                "canal": "EMAIL",
                "destinatario": destinatario,
                "asunto": asunto,
                "contenido": contenido,
                "estado": "PENDING",
                "clave_idempotencia": clave_idempotencia,
            }
        )
        if not config or not config.get("activo"):
            return self.notifications_repo.mark_failed(notification["id"], "SMTP no configurado o inactivo")

        try:
            self._send_smtp(config, destinatario, asunto, contenido, contenido_texto)
        except Exception as exc:  # noqa: BLE001
            self.notifications_repo.mark_failed(notification["id"], str(exc))
            return self.notifications_repo.get_by_idempotency(clave_idempotencia) if clave_idempotencia else {"id": notification["id"], "estado": "FAILED"}

        now = datetime.now(timezone.utc).isoformat()
        return self.notifications_repo.mark_sent(notification["id"], now)

    def send_test(self, auth: AuthContext, email: str, asunto: Optional[str], mensaje: Optional[str]) -> dict:
        subject = asunto or "Notificación de prueba"
        body = mensaje or "Este es un correo de prueba del sistema."
        return self.send_email(
            auth,
            destinatario=email,
            asunto=subject,
            contenido=body,
            contenido_texto=body,
            tipo="SYSTEM",
            clave_idempotencia=f"test-{email}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        )