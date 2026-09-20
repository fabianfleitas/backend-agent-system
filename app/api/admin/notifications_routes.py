from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import AuthContext, get_admin_auth
from app.schemas.admin import NotificationOut, SendTestIn, SmtpConfigIn, SmtpConfigOut
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.services.notification_service import NotificationService

router = APIRouter()


def _get_service() -> NotificationService:
    return NotificationService()


def _smtp_out(c: dict) -> SmtpConfigOut:
    return SmtpConfigOut(
        institucion_id=c.get("institucion_id"),
        servidor=c.get("servidor") or "",
        puerto=int(c.get("puerto") or 587),
        cifrado=c.get("cifrado") or "STARTTLS",
        usuario=c.get("usuario"),
        correo_remitente=c.get("correo_remitente") or "",
        nombre_remitente=c.get("nombre_remitente"),
        timeout_segundos=int(c.get("timeout_segundos") or 30),
        activo=c.get("activo", True),
    )


def _notification_out(n: dict) -> NotificationOut:
    return NotificationOut(
        id=n["id"],
        institucion_id=n.get("institucion_id"),
        tipo=n.get("tipo") or "SYSTEM",
        canal=n.get("canal") or "EMAIL",
        destinatario=n.get("destinatario") or "",
        asunto=n.get("asunto"),
        contenido=n.get("contenido"),
        estado=n.get("estado") or "PENDING",
        fecha_programada=str(n.get("fecha_programada")) if n.get("fecha_programada") else None,
        fecha_envio=str(n.get("fecha_envio")) if n.get("fecha_envio") else None,
        error=n.get("error"),
        created_at=str(n.get("created_at")) if n.get("created_at") else None,
    )


@router.get("/smtp", response_model=SmtpConfigOut)
def get_smtp(auth: AuthContext = Depends(get_admin_auth)) -> SmtpConfigOut:
    config = _get_service().get_smtp_config(auth)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMTP no configurado")
    return _smtp_out(config)


@router.put("/smtp", response_model=SmtpConfigOut)
def update_smtp(
    payload: SmtpConfigIn,
    auth: AuthContext = Depends(get_admin_auth),
) -> SmtpConfigOut:
    try:
        config = _get_service().update_smtp_config(auth, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return _smtp_out(config)


@router.get("/notifications", response_model=PaginatedResponse[NotificationOut])
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_admin_auth),
) -> PaginatedResponse[NotificationOut]:
    rows = _get_service().list_notifications(auth)
    total = len(rows)
    page = rows[offset : offset + limit]
    return PaginatedResponse[NotificationOut](
        items=[_notification_out(n) for n in page],
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post("/notifications/send-test", response_model=NotificationOut)
def send_test(
    payload: SendTestIn,
    auth: AuthContext = Depends(get_admin_auth),
) -> NotificationOut:
    notification = _get_service().send_test(auth, payload.email, payload.asunto, payload.mensaje)
    return _notification_out(notification)