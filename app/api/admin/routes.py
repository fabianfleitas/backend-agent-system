from __future__ import annotations

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.security import AuthContext, get_auth_context, require_admin
from app.schemas.admin import (
    AdminAuditOut,
    AdminListDocumentsOut,
    AdminReindexIn,
    AdminReindexOut,
    AdminUploadDocumentOut,
)
from app.schemas.common import AuditLogOut, DocumentOut, DocumentVersionOut
from app.services.mock_store import store
from app.utils.files import ensure_dir, safe_join, write_bytes


router = APIRouter()


def _doc_out(d, v) -> DocumentOut:
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
    return DocumentVersionOut(
        id=v.id,
        documento_id=v.documento_id,
        numero_version=v.numero_version,
        ruta_archivo=v.ruta_archivo,
        estado_indexacion=v.estado_indexacion,
        es_version_activa=v.es_version_activa,
        total_chunks=v.total_chunks,
        fecha_carga=v.fecha_carga,
        fecha_indexacion=v.fecha_indexacion,
        cargado_por_external_auth_id=v.cargado_por_external_auth_id,
    )


def _audit_out(a) -> AuditLogOut:
    return AuditLogOut(
        id=a.id,
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
    ensure_dir(settings.storage_documents_dir)

    ext = os.path.splitext(file.filename or "")[1] or ".pdf"
    filename = f"{uuid.uuid4().hex}{ext}"
    doc_path = safe_join(settings.storage_documents_dir, filename)
    write_bytes(doc_path, file_bytes)

    doc, version = store.create_document(
        categoria_id=categoria_id,
        codigo_documento=codigo_documento,
        titulo=titulo,
        descripcion=descripcion,
        cargado_por_external_auth_id=auth.external_auth_id,
        ruta_archivo=doc_path,
    )

    return AdminUploadDocumentOut(
        document=_doc_out(doc, version),
        version=_version_out(version),
    )


@router.get("/documents", response_model=AdminListDocumentsOut)
def list_documents(auth: AuthContext = Depends(get_auth_context)) -> AdminListDocumentsOut:
    require_admin(auth)
    items = store.list_documents()
    return AdminListDocumentsOut(documents=[_doc_out(d, v) for d, v in items])


@router.post("/reindex", response_model=AdminReindexOut)
def reindex(payload: AdminReindexIn, auth: AuthContext = Depends(get_auth_context)) -> AdminReindexOut:
    require_admin(auth)
    updated = store.reindex(documento_id=payload.documento_id)
    return AdminReindexOut(updated_versions=updated)


@router.get("/audit", response_model=AdminAuditOut)
def get_audit(auth: AuthContext = Depends(get_auth_context)) -> AdminAuditOut:
    require_admin(auth)
    logs = store.list_audit_logs()
    return AdminAuditOut(logs=[_audit_out(a) for a in logs])
