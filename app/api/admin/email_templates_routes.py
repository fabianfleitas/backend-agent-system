from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import AuthContext, get_admin_auth
from app.schemas.admin import EmailTemplateIn, EmailTemplateOut
from app.services.email_template_service import EmailTemplateService

router = APIRouter()


def _get_service() -> EmailTemplateService:
    return EmailTemplateService()


def _out(t: dict) -> EmailTemplateOut:
    return EmailTemplateOut(
        id=t["id"],
        institucion_id=t.get("institucion_id"),
        codigo=t.get("codigo") or "",
        nombre=t.get("nombre") or "",
        asunto=t.get("asunto") or "",
        contenido_html=t.get("contenido_html"),
        contenido_texto=t.get("contenido_texto"),
        activo=t.get("activo", True),
        created_at=str(t.get("created_at")) if t.get("created_at") else None,
        updated_at=str(t.get("updated_at")) if t.get("updated_at") else None,
    )


@router.get("/email-templates", response_model=list[EmailTemplateOut])
def list_templates(auth: AuthContext = Depends(get_admin_auth)) -> list[EmailTemplateOut]:
    rows = _get_service().list(auth)
    return [_out(r) for r in rows]


@router.post("/email-templates", response_model=EmailTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: EmailTemplateIn,
    auth: AuthContext = Depends(get_admin_auth),
) -> EmailTemplateOut:
    row = _get_service().create(auth, payload)
    return _out(row)


@router.put("/email-templates/{template_id}", response_model=EmailTemplateOut)
def update_template(
    template_id: int,
    payload: EmailTemplateIn,
    auth: AuthContext = Depends(get_admin_auth),
) -> EmailTemplateOut:
    row = _get_service().update(auth, template_id, payload)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    return _out(row)


@router.delete("/email-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_template(
    template_id: int,
    auth: AuthContext = Depends(get_admin_auth),
) -> None:
    row = _get_service().deactivate(auth, template_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")