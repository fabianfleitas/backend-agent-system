from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.admin.routes import _audit_out, get_admin_auth
from app.core.security import AuthContext, get_auth_context, get_platform_admin_auth, require_platform_admin
from app.repositories.audit_repository import AuditRepository
from app.schemas.admin import (
    InstitutionIn,
    InstitutionOut,
    MemberIn,
    MemberOut,
    PlanIn,
    PlanOut,
    SubscriptionOut,
    PagoOut,
    ComprobanteOut,
)
from app.schemas.common import AuditLogOut, PaginatedResponse, PaginationMeta, UserOut
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.common import AuditLogOut, UserOut
from app.schemas.system import MetricsOut
from app.utils.csv_export import csv_response, metrics_to_csv, to_csv
from app.services.platform_service import PlatformService

router = APIRouter()


def _get_plat_service() -> PlatformService:
    return PlatformService()


def _plan_out(p: dict) -> PlanOut:
    return PlanOut(
        id=p.get("id"),
        codigo=p.get("codigo"),
        nombre=p.get("nombre") or "",
        descripcion=p.get("descripcion"),
        precio=p.get("precio"),
        moneda=p.get("moneda"),
        intervalo=p.get("intervalo"),
        max_documentos=p.get("max_documentos"),
        max_usuarios=p.get("max_usuarios"),
        max_estudiantes=p.get("max_estudiantes"),
        features=p.get("features") if isinstance(p.get("features"), dict) else None,
        activo=p.get("activo", True),
        created_at=str(p.get("created_at")) if p.get("created_at") else None,
        updated_at=str(p.get("updated_at")) if p.get("updated_at") else None,
    )


def _institution_out(i: dict) -> InstitutionOut:
    return InstitutionOut(
        id=i.get("id"),
        codigo=i.get("codigo"),
        nombre=i.get("nombre") or "",
        nombre_comercial=i.get("nombre_comercial"),
        ciudad=i.get("ciudad"),
        pais=i.get("pais"),
        direccion=i.get("direccion"),
        email_contacto=i.get("email_contacto"),
        telefono_contacto=i.get("telefono_contacto"),
        activo=i.get("activo", True),
        stripe_customer_id=i.get("stripe_customer_id"),
        created_at=str(i.get("created_at")) if i.get("created_at") else None,
        updated_at=str(i.get("updated_at")) if i.get("updated_at") else None,
    )


@router.get("/institutions", response_model=list[InstitutionOut])
def list_institutions(
    auth: AuthContext = Depends(get_platform_admin_auth),
    activo: bool = Query(default=True),
    service: PlatformService = Depends(_get_plat_service),
) -> list[InstitutionOut]:
    rows = service.list_institutions(activo=activo)
    return [_institution_out(r) for r in rows]


@router.get("/institutions/{institucion_id}", response_model=InstitutionOut)
def get_institution(
    institucion_id: int,
    auth: AuthContext = Depends(get_platform_admin_auth),
    service: PlatformService = Depends(_get_plat_service),
) -> InstitutionOut:
    row = service.get_institution(institucion_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")
    return _institution_out(row)


@router.post("/institutions", response_model=InstitutionOut, status_code=status.HTTP_201_CREATED)
def create_institution(
    payload: InstitutionIn,
    auth: AuthContext = Depends(get_platform_admin_auth),
    service: PlatformService = Depends(_get_plat_service),
) -> InstitutionOut:
    row = service.create_institution(**payload.model_dump())
    return _institution_out(row)


@router.put("/institutions/{institucion_id}", response_model=InstitutionOut)
def update_institution(
    institucion_id: int,
    payload: InstitutionIn,
    auth: AuthContext = Depends(get_platform_admin_auth),
    service: PlatformService = Depends(_get_plat_service),
) -> InstitutionOut:
    row = service.update_institution(institucion_id, **payload.model_dump())
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")
    return _institution_out(row)


@router.delete("/institutions/{institucion_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_institution(
    institucion_id: int,
    auth: AuthContext = Depends(get_platform_admin_auth),
    service: PlatformService = Depends(_get_plat_service),
) -> None:
    row = service.deactivate_institution(institucion_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")


@router.get("/institutions/{institucion_id}/members", response_model=list[MemberOut])
def list_members(
    institucion_id: int,
    auth: AuthContext = Depends(get_platform_admin_auth),
    service: PlatformService = Depends(_get_plat_service),
) -> list[MemberOut]:
    rows = service.list_members(institucion_id)
    return [
        MemberOut(
            id=r.get("id"),
            external_auth_id=r.get("external_auth_id"),
            tipo_miembro=r.get("tipo_miembro"),
            activo=r.get("activo", True),
            fecha_ingreso=str(r.get("fecha_ingreso")) if r.get("fecha_ingreso") else None,
            email=(r.get("app_users") or {}).get("email") if isinstance(r.get("app_users"), dict) else r.get("email"),
            full_name=(r.get("app_users") or {}).get("full_name") if isinstance(r.get("app_users"), dict) else r.get("full_name"),
        )
        for r in rows
    ]


@router.post("/institutions/{institucion_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    institucion_id: int,
    payload: MemberIn,
    auth: AuthContext = Depends(get_platform_admin_auth),
    service: PlatformService = Depends(_get_plat_service),
) -> MemberOut:
    try:
        row = service.add_member(institucion_id, payload.external_auth_id, payload.tipo_miembro)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return MemberOut(
        id=row.get("id"),
        external_auth_id=row.get("external_auth_id"),
        tipo_miembro=row.get("tipo_miembro"),
        activo=True,
        fecha_ingreso=str(row.get("fecha_ingreso")) if row.get("fecha_ingreso") else None,
    )


@router.delete("/institutions/{institucion_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_member(
    institucion_id: int,
    member_id: int,
    auth: AuthContext = Depends(get_platform_admin_auth),
    service: PlatformService = Depends(_get_plat_service),
) -> None:
    service.deactivate_member(member_id)


@router.get("/users", response_model=PaginatedResponse[UserOut])
def list_users(
    auth: AuthContext = Depends(get_platform_admin_auth),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: PlatformService = Depends(_get_plat_service),
) -> PaginatedResponse[UserOut]:
    users = service.list_users(auth)
    total = len(users)
    page = users[offset : offset + limit]
    return PaginatedResponse[UserOut](
        items=page,
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/metrics", response_model=MetricsOut)
def get_metrics(
    auth: AuthContext = Depends(get_platform_admin_auth),
    desde: Optional[str] = Query(default=None),
    hasta: Optional[str] = Query(default=None),
    categoria_id: Optional[int] = Query(default=None),
    modelo: Optional[str] = Query(default=None),
    documento_id: Optional[int] = Query(default=None),
    granularidad: Optional[str] = Query(default="day"),
    service: PlatformService = Depends(_get_plat_service),
) -> MetricsOut:
    return service.get_metrics(auth, desde=desde, hasta=hasta, categoria_id=categoria_id, modelo=modelo, documento_id=documento_id, granularidad=granularidad)


@router.get("/audit", response_model=PaginatedResponse[AuditLogOut])
def get_audit(
    auth: AuthContext = Depends(get_platform_admin_auth),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    desde: Optional[str] = Query(default=None),
    hasta: Optional[str] = Query(default=None),
    modelo: Optional[str] = Query(default=None),
    service: PlatformService = Depends(_get_plat_service),
) -> PaginatedResponse[AuditLogOut]:
    logs = service.list_audit_logs(auth, desde=desde, hasta=hasta, modelo=modelo)
    total = len(logs)
    page = logs[offset : offset + limit]
    return PaginatedResponse[AuditLogOut](
        items=[_audit_out(a) for a in page],
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/audit/export")
def export_audit_platform(auth: AuthContext = Depends(get_platform_admin_auth)) -> Response:
    logs = _get_plat_service().list_audit_logs(auth)
    return csv_response(to_csv(logs, ["id", "mensaje_id", "score_fidelidad", "score_relevancia", "score_contexto", "observaciones", "fecha_evaluacion"]), "audit.csv")


@router.get("/comprobantes/export")
def export_comprobantes_platform(auth: AuthContext = Depends(get_platform_admin_auth)) -> Response:
    from app.repositories.billing_repository import BillingRepository
    rows = BillingRepository().list_comprobantes()
    return csv_response(to_csv(rows, ["id", "institucion_id", "pago_id", "tipo_comprobante", "numero", "estado", "importe", "moneda", "referencia_externa", "fecha_emision"]), "comprobantes.csv")


@router.get("/metrics/export")
def export_metrics_platform(auth: AuthContext = Depends(get_platform_admin_auth)) -> Response:
    m = _get_plat_service().get_metrics(auth)
    return csv_response(metrics_to_csv(m), "metrics.csv")


# --- Billing lectura global (platform) ---
@router.get("/plans", response_model=list[PlanOut])
def list_plans(
    auth: AuthContext = Depends(get_platform_admin_auth),
    service: PlatformService = Depends(_get_plat_service),
) -> list[PlanOut]:
    from app.repositories.billing_repository import BillingRepository
    rows = BillingRepository().list_planes()
    return [
        PlanOut(
            id=r.get("id"),
            codigo=r.get("codigo"),
            nombre=r.get("nombre") or "",
            descripcion=r.get("descripcion"),
            precio=r.get("precio"),
            moneda=r.get("moneda"),
            intervalo=r.get("intervalo"),
            max_documentos=r.get("max_documentos"),
            max_usuarios=r.get("max_usuarios"),
            max_estudiantes=r.get("max_estudiantes"),
            features=r.get("features") if isinstance(r.get("features"), dict) else None,
            activo=r.get("activo", True),
            created_at=str(r.get("created_at")) if r.get("created_at") else None,
            updated_at=str(r.get("updated_at")) if r.get("updated_at") else None,
        ) for r in rows
    ]


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanIn,
    auth: AuthContext = Depends(get_platform_admin_auth),
    service: PlatformService = Depends(_get_plat_service),
) -> PlanOut:
    row = service.create_plan(**payload.model_dump())
    return _plan_out(row)


@router.put("/plans/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: int,
    payload: PlanIn,
    auth: AuthContext = Depends(get_platform_admin_auth),
    service: PlatformService = Depends(_get_plat_service),
) -> PlanOut:
    row = service.update_plan(plan_id, **payload.model_dump())
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return _plan_out(row)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_plan(
    plan_id: int,
    auth: AuthContext = Depends(get_platform_admin_auth),
    service: PlatformService = Depends(_get_plat_service),
) -> None:
    row = service.deactivate_plan(plan_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")


@router.get("/subscriptions", response_model=PaginatedResponse[SubscriptionOut])
def list_subscriptions_platform(
    auth: AuthContext = Depends(get_platform_admin_auth),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: PlatformService = Depends(_get_plat_service),
) -> PaginatedResponse[SubscriptionOut]:
    from app.repositories.billing_repository import BillingRepository
    rows = BillingRepository().list_subscriptions()
    total = len(rows)
    page = rows[offset:offset+limit]
    return PaginatedResponse[SubscriptionOut](
        items=[
            SubscriptionOut(
                id=r.get("id"),
                institucion_id=r.get("institucion_id"),
                plan_id=r.get("plan_id"),
                estado=r.get("estado"),
                fecha_inicio=str(r.get("fecha_inicio")) if r.get("fecha_inicio") else None,
                fecha_vencimiento=str(r.get("fecha_vencimiento")) if r.get("fecha_vencimiento") else None,
                fecha_cancelacion=str(r.get("fecha_cancelacion")) if r.get("fecha_cancelacion") else None,
                cancelacion_programada=r.get("cancelacion_programada") or False,
                auto_renovacion=r.get("auto_renovacion") or False,
                periodo_prueba_inicio=str(r.get("periodo_prueba_inicio")) if r.get("periodo_prueba_inicio") else None,
                periodo_prueba_fin=str(r.get("periodo_prueba_fin")) if r.get("periodo_prueba_fin") else None,
                stripe_subscription_id=r.get("stripe_subscription_id"),
                stripe_customer_id=r.get("stripe_customer_id"),
                plan=_plan_out(r.get("planes")) if isinstance(r.get("planes"), dict) else None,
                created_at=str(r.get("created_at")) if r.get("created_at") else None,
                updated_at=str(r.get("updated_at")) if r.get("updated_at") else None,
            ) for r in page
        ],
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/pagos", response_model=PaginatedResponse[PagoOut])
def list_pagos_platform(
    auth: AuthContext = Depends(get_platform_admin_auth),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: PlatformService = Depends(_get_plat_service),
) -> PaginatedResponse[PagoOut]:
    from app.repositories.billing_repository import BillingRepository
    rows = BillingRepository().list_pagos()
    total = len(rows)
    page = rows[offset:offset+limit]
    return PaginatedResponse[PagoOut](
        items=[
            PagoOut(
                id=r.get("id"),
                institucion_id=r.get("institucion_id"),
                suscripcion_id=r.get("suscripcion_id"),
                importe=r.get("importe"),
                moneda=r.get("moneda"),
                estado=r.get("estado"),
                proveedor=r.get("proveedor"),
                descripcion=r.get("descripcion"),
                fecha_pago=str(r.get("fecha_pago")) if r.get("fecha_pago") else None,
                created_at=str(r.get("created_at")) if r.get("created_at") else None,
            ) for r in page
        ],
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/comprobantes", response_model=PaginatedResponse[ComprobanteOut])
def list_comprobantes_platform(
    auth: AuthContext = Depends(get_platform_admin_auth),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: PlatformService = Depends(_get_plat_service),
) -> PaginatedResponse[ComprobanteOut]:
    from app.repositories.billing_repository import BillingRepository
    rows = BillingRepository().list_comprobantes()
    total = len(rows)
    page = rows[offset:offset+limit]
    return PaginatedResponse[ComprobanteOut](
        items=[
            ComprobanteOut(
                id=r.get("id"),
                institucion_id=r.get("institucion_id"),
                pago_id=r.get("pago_id"),
                tipo_comprobante=r.get("tipo_comprobante"),
                numero=r.get("numero"),
                estado=r.get("estado"),
                importe=r.get("importe"),
                moneda=r.get("moneda"),
                archivo_path=r.get("archivo_path"),
                proveedor=r.get("proveedor"),
                referencia_externa=r.get("referencia_externa"),
                fecha_emision=str(r.get("fecha_emision")) if r.get("fecha_emision") else None,
                created_at=str(r.get("created_at")) if r.get("created_at") else None,
            ) for r in page
        ],
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )
