from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.core.security import AuthContext, get_admin_auth, require_institution_admin
from app.schemas.admin import (
    AdminReindexIn,
    AdminReindexOut,
    AdminUploadDocumentOut,
    AdminUploadVersionOut,
    ComprobanteOut,
    ConfigParamIn,
    ConfigParamOut,
    DocumentDetailOut,
    PagoOut,
    PlanOut,
    SubscriptionOut,
)
from app.schemas.common import (
    AuditLogOut,
    DocumentOut,
    DocumentStatus,
    DocumentVersionOut,
    PaginatedResponse,
    PaginationMeta,
    UserOut,
    UserRole,
)
from app.schemas.system import MetricsOut
from app.services.admin_service import AdminService
from app.services.audit_service import AuditService
from app.services.documents_service import DocumentsService


router = APIRouter()


def _doc_out(d, v) -> DocumentOut:
    if isinstance(d, dict):
        version_activa = _version_out(v) if v else None
        return DocumentOut(
            id=d["id"],
            categoria_id=d.get("categoria_id"),
            codigo_documento=d.get("codigo_documento"),
            titulo=d["titulo"],
            descripcion=d.get("descripcion"),
            activo=d["activo"],
            fecha_creacion=d["fecha_creacion"],
            version_activa=version_activa,
        )
    version_activa = _version_out(v) if v else None
    return DocumentOut(
        id=d.id,
        categoria_id=d.categoria_id,
        codigo_documento=d.codigo_documento,
        titulo=d.titulo,
        descripcion=d.descripcion,
        activo=d.activo,
        fecha_creacion=d.fecha_creacion,
        version_activa=version_activa,
    )


def _version_out(v) -> DocumentVersionOut:
    if isinstance(v, dict):
        status_val = DocumentStatus(v["status"]) if v.get("status") else DocumentStatus.PENDING
        return DocumentVersionOut(
            id=v["id"],
            documento_id=v["documento_id"],
            numero_version=v["numero_version"],
            ruta_archivo=v["ruta_archivo"],
            status=status_val,
            es_version_activa=v["es_version_activa"],
            total_chunks=v["total_chunks"],
            embedding_model=v.get("embedding_model"),
            fecha_carga=v["fecha_carga"],
            indexed_at=v.get("indexed_at"),
            cargado_por_external_auth_id=v["cargado_por_external_auth_id"],
        )
    status_val = DocumentStatus(v.status) if v.status else DocumentStatus.PENDING
    return DocumentVersionOut(
        id=v.id,
        documento_id=v.documento_id,
        numero_version=v.numero_version,
        ruta_archivo=v.ruta_archivo,
        status=status_val,
        es_version_activa=v.es_version_activa,
        total_chunks=v.total_chunks,
        embedding_model=v.embedding_model,
        fecha_carga=v.fecha_carga,
        indexed_at=v.indexed_at,
        cargado_por_external_auth_id=v.cargado_por_external_auth_id,
    )


def _audit_out(a) -> AuditLogOut:
    if isinstance(a, dict):
        return AuditLogOut(
            id=uuid.UUID(a["id"]),
            mensaje_id=a["mensaje_id"],
            score_fidelidad=float(a["score_fidelidad"]) if a.get("score_fidelidad") is not None else None,
            score_relevancia=float(a["score_relevancia"]) if a.get("score_relevancia") is not None else None,
            score_contexto=float(a["score_contexto"]) if a.get("score_contexto") is not None else None,
            observaciones=a.get("observaciones"),
            fecha_evaluacion=a["fecha_evaluacion"],
        )
    return AuditLogOut(
        id=uuid.UUID(a.id),
        mensaje_id=a.mensaje_id,
        score_fidelidad=a.score_fidelidad,
        score_relevancia=a.score_relevancia,
        score_contexto=a.score_contexto,
        observaciones=a.observaciones,
        fecha_evaluacion=a.fecha_evaluacion,
    )


@router.post("/documents", response_model=AdminUploadDocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    titulo: str = Form(...),
    descripcion: Optional[str] = Form(default=None),
    categoria_id: Optional[int] = Form(default=None),
    codigo_documento: Optional[str] = Form(default=None),
    auth: AuthContext = Depends(get_admin_auth),
) -> AdminUploadDocumentOut:

    file_bytes = await file.read()
    doc, version = DocumentsService().upload_document(
        auth=auth,
        file_bytes=file_bytes,
        filename=file.filename,
        content_type=file.content_type,
        titulo=titulo,
        descripcion=descripcion,
        categoria_id=categoria_id,
        codigo_documento=codigo_documento,
    )

    return AdminUploadDocumentOut(
        document=_doc_out(doc, version),
        version=_version_out(version),
    )


@router.get("/documents/{documento_id}", response_model=DocumentDetailOut)
def get_document(
    documento_id: int,
    auth: AuthContext = Depends(get_admin_auth),
) -> DocumentDetailOut:
    result = DocumentsService().get_document(documento_id, auth)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    doc, versions = result
    return DocumentDetailOut(
        id=doc["id"],
        categoria_id=doc.get("categoria_id"),
        codigo_documento=doc.get("codigo_documento"),
        titulo=doc["titulo"],
        descripcion=doc.get("descripcion"),
        activo=doc["activo"],
        fecha_creacion=doc["fecha_creacion"],
        versiones=[_version_out(v) for v in versions],
    )


@router.delete("/documents/{documento_id}", response_model=DocumentOut)
def deactivate_document(
    documento_id: int,
    auth: AuthContext = Depends(get_admin_auth),
) -> DocumentOut:
    result = DocumentsService().deactivate_document(documento_id, auth)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or already inactive")
    doc, version = result
    return _doc_out(doc, version)


@router.post(
    "/documents/{documento_id}/versions",
    response_model=AdminUploadVersionOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_new_version(
    documento_id: int,
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_admin_auth),
) -> AdminUploadVersionOut:

    file_bytes = await file.read()
    try:
        doc, version = DocumentsService().upload_new_version(
            documento_id=documento_id,
            auth=auth,
            file_bytes=file_bytes,
            filename=file.filename,
            content_type=file.content_type,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return AdminUploadVersionOut(
        document=_doc_out(doc, version),
        version=_version_out(version),
    )


@router.get("/documents", response_model=PaginatedResponse[DocumentOut])
def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_admin_auth),
) -> PaginatedResponse[DocumentOut]:
    items = DocumentsService().list_documents(auth)
    total = len(items)
    page = items[offset : offset + limit]
    return PaginatedResponse[DocumentOut](
        items=[_doc_out(d, v) for d, v in page],
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post("/reindex", response_model=AdminReindexOut)
def reindex(payload: AdminReindexIn, auth: AuthContext = Depends(get_admin_auth)) -> AdminReindexOut:
    try:
        updated = DocumentsService().reindex(documento_id=payload.documento_id, auth=auth)
    except Exception as exc:
        if "updated_at" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Supabase schema mismatch: documento_versiones necesita la columna "
                    "updated_at porque existe el trigger trg_documento_versiones_updated_at."
                ),
            ) from exc
        raise
    return AdminReindexOut(updated_versions=updated)


@router.get("/audit", response_model=PaginatedResponse[AuditLogOut])
def get_audit(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_admin_auth),
) -> PaginatedResponse[AuditLogOut]:
    logs = AuditService().list_audit_logs(auth)
    total = len(logs)
    page = logs[offset : offset + limit]
    return PaginatedResponse[AuditLogOut](
        items=[_audit_out(a) for a in page],
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/users", response_model=PaginatedResponse[UserOut])
def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_admin_auth),
) -> PaginatedResponse[UserOut]:
    users = AdminService().list_users(auth)
    total = len(users)
    page = users[offset : offset + limit]
    return PaginatedResponse[UserOut](
        items=page,
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/metrics", response_model=MetricsOut)
def get_metrics(
    auth: AuthContext = Depends(get_admin_auth),
    desde: Optional[str] = Query(default=None),
    hasta: Optional[str] = Query(default=None),
    categoria_id: Optional[int] = Query(default=None),
    modelo: Optional[str] = Query(default=None),
    documento_id: Optional[int] = Query(default=None),
    granularidad: Optional[str] = Query(default="day"),
) -> MetricsOut:
    return AdminService().get_metrics(
        auth,
        desde=desde,
        hasta=hasta,
        categoria_id=categoria_id,
        modelo=modelo,
        documento_id=documento_id,
        granularidad=granularidad,
    )


@router.get("/config", response_model=List[ConfigParamOut])
def list_config(auth: AuthContext = Depends(get_admin_auth)) -> List[ConfigParamOut]:
    from app.repositories.config_repository import ConfigParametersRepository
    repo = ConfigParametersRepository()
    inst_id = auth.institucion_id if not auth.is_platform_admin else None
    rows = repo.list_by_institution(inst_id) if inst_id else repo.list_params()
    # For dashboard: include institutional + global; filter active only; respect precedence manually handled by repo
    return [
        ConfigParamOut(
            id=r.get("id"),
            institucion_id=r.get("institucion_id"),
            clave=r.get("clave"),
            valor=r.get("valor"),
            tipo=r.get("tipo"),
            descripcion=r.get("descripcion"),
            editable_desde_dashboard=r.get("editable_desde_dashboard", True),
            activo=r.get("activo", True),
            created_at=str(r.get("created_at")) if r.get("created_at") else None,
            updated_at=str(r.get("updated_at")) if r.get("updated_at") else None,
        )
        for r in rows if r.get("activo") is not False
    ]


@router.put("/config/{clave}", response_model=ConfigParamOut)
def update_config(
    clave: str,
    payload: ConfigParamIn,
    auth: AuthContext = Depends(get_admin_auth),
) -> ConfigParamOut:
    # Institucional no puede editar globales (institucion_id NULL); plataforma sí puede editar globales
    from app.repositories.config_repository import ConfigParametersRepository
    repo = ConfigParametersRepository()
    # Check existing row
    existing = repo.get_param(clave, auth.institucion_id if not auth.is_platform_admin else None)
    # If institutional admin tries to modify a global (institucion_id NULL), block
    # If row is not editable_desde_dashboard, block
    if existing and existing.get("editable_desde_dashboard") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not editable from dashboard")
    if not auth.is_platform_admin and existing and existing.get("institucion_id") is None:
        # Institutional admin cannot modify global defaults
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Global params can only be edited at platform level")
    result = repo.set_param(
        clave=clave,
        valor=str(payload.valor),
        tipo=payload.tipo,
        institucion_id=auth.institucion_id if not auth.is_platform_admin else None,
        descripcion=payload.descripcion,
    )
    # Auditoría de cambio de configuración
    try:
        from app.repositories.audit_repository import AuditRepository
        audit_repo = AuditRepository()
        audit_repo.create_audit_log(
            conversation_id=0,
            message_id=0,
            external_auth_id=auth.external_auth_id,
            respuesta_texto="CONFIG_UPDATE",
            proveedor_ia=None,
            modelo_ia=None,
            tokens_input=None,
            tokens_output=None,
            tiempo_respuesta_ms=None,
            observaciones=f"CONFIG_UPDATE clave={clave} tipo={payload.tipo} valor={str(payload.valor)[:200]} (global={auth.is_platform_admin})",
            institucion_id=auth.institucion_id,
        )
    except Exception:
        pass  # No bloquear actualización por fallo de auditoría
    if not result:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Update failed")
    return ConfigParamOut(
        id=result.get("id"),
        institucion_id=result.get("institucion_id"),
        clave=result.get("clave"),
        valor=result.get("valor"),
        tipo=result.get("tipo"),
        descripcion=result.get("descripcion"),
        editable_desde_dashboard=result.get("editable_desde_dashboard", True),
        activo=result.get("activo", True),
        created_at=str(result.get("created_at")) if result.get("created_at") else None,
        updated_at=str(result.get("updated_at")) if result.get("updated_at") else None,
    )


# --- Billing lectura institucional ---
@router.get("/subscription", response_model=SubscriptionOut)
def get_subscription(
    auth: AuthContext = Depends(get_admin_auth),
) -> SubscriptionOut:
    from app.services.billing_service import BillingService
    sub = BillingService().get_subscription(auth)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    plan = BillingService().get_plan_for_subscription(auth)
    return SubscriptionOut(
        id=sub.get("id"),
        institucion_id=sub.get("institucion_id"),
        plan_id=sub.get("plan_id"),
        estado=sub.get("estado"),
        fecha_inicio=str(sub.get("fecha_inicio")) if sub.get("fecha_inicio") else None,
        fecha_vencimiento=str(sub.get("fecha_vencimiento")) if sub.get("fecha_vencimiento") else None,
        fecha_cancelacion=str(sub.get("fecha_cancelacion")) if sub.get("fecha_cancelacion") else None,
        cancelacion_programada=sub.get("cancelacion_programada") or False,
        auto_renovacion=sub.get("auto_renovacion") or False,
        periodo_prueba_inicio=str(sub.get("periodo_prueba_inicio")) if sub.get("periodo_prueba_inicio") else None,
        periodo_prueba_fin=str(sub.get("periodo_prueba_fin")) if sub.get("periodo_prueba_fin") else None,
        stripe_subscription_id=sub.get("stripe_subscription_id"),
        stripe_customer_id=sub.get("stripe_customer_id"),
        plan=PlanOut(
            id=plan.get("id"),
            codigo=plan.get("codigo"),
            nombre=plan.get("nombre") or "",
            descripcion=plan.get("descripcion"),
            precio=plan.get("precio"),
            moneda=plan.get("moneda"),
            intervalo=plan.get("intervalo"),
            max_documentos=plan.get("max_documentos"),
            max_usuarios=plan.get("max_usuarios"),
            max_estudiantes=plan.get("max_estudiantes"),
            features=plan.get("features") if isinstance(plan.get("features"), dict) else None,
            activo=plan.get("activo", True),
            created_at=str(plan.get("created_at")) if plan.get("created_at") else None,
            updated_at=str(plan.get("updated_at")) if plan.get("updated_at") else None,
        ) if plan else None,
        created_at=str(sub.get("created_at")) if sub.get("created_at") else None,
        updated_at=str(sub.get("updated_at")) if sub.get("updated_at") else None,
    )


@router.get("/plan", response_model=PlanOut)
def get_plan(
    auth: AuthContext = Depends(get_admin_auth),
) -> PlanOut:
    from app.services.billing_service import BillingService
    plan = BillingService().get_plan_for_subscription(auth)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return PlanOut(
        id=plan.get("id"),
        codigo=plan.get("codigo"),
        nombre=plan.get("nombre") or "",
        descripcion=plan.get("descripcion"),
        precio=plan.get("precio"),
        moneda=plan.get("moneda"),
        intervalo=plan.get("intervalo"),
        max_documentos=plan.get("max_documentos"),
        max_usuarios=plan.get("max_usuarios"),
        max_estudiantes=plan.get("max_estudiantes"),
        features=plan.get("features") if isinstance(plan.get("features"), dict) else None,
        activo=plan.get("activo", True),
        created_at=str(plan.get("created_at")) if plan.get("created_at") else None,
        updated_at=str(plan.get("updated_at")) if plan.get("updated_at") else None,
    )


@router.get("/pagos", response_model=PaginatedResponse[PagoOut])
def list_pagos(
    auth: AuthContext = Depends(get_admin_auth),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[PagoOut]:
    from app.services.billing_service import BillingService
    rows = BillingService().list_pagos(auth)
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
def list_comprobantes(
    auth: AuthContext = Depends(get_admin_auth),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[ComprobanteOut]:
    from app.services.billing_service import BillingService
    rows = BillingService().list_comprobantes(auth)
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
