from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.core.security import AuthContext, get_auth_context, require_admin
from app.schemas.admin import (
    AdminReindexIn,
    AdminReindexOut,
    AdminUploadDocumentOut,
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
    auth: AuthContext = Depends(get_auth_context),
) -> AdminUploadDocumentOut:
    require_admin(auth)

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


@router.get("/documents", response_model=PaginatedResponse[DocumentOut])
def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_auth_context),
) -> PaginatedResponse[DocumentOut]:
    require_admin(auth)
    items = DocumentsService().list_documents()
    total = len(items)
    page = items[offset : offset + limit]
    return PaginatedResponse[DocumentOut](
        items=[_doc_out(d, v) for d, v in page],
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post("/reindex", response_model=AdminReindexOut)
def reindex(payload: AdminReindexIn, auth: AuthContext = Depends(get_auth_context)) -> AdminReindexOut:
    require_admin(auth)
    try:
        updated = DocumentsService().reindex(documento_id=payload.documento_id)
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
    auth: AuthContext = Depends(get_auth_context),
) -> PaginatedResponse[AuditLogOut]:
    require_admin(auth)
    logs = AuditService().list_audit_logs()
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
    auth: AuthContext = Depends(get_auth_context),
) -> PaginatedResponse[UserOut]:
    require_admin(auth)
    users = AdminService().list_users()
    total = len(users)
    page = users[offset : offset + limit]
    return PaginatedResponse[UserOut](
        items=page,
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/metrics", response_model=MetricsOut)
def get_metrics(auth: AuthContext = Depends(get_auth_context)) -> MetricsOut:
    require_admin(auth)
    return AdminService().get_metrics()
