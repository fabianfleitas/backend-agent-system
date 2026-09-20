from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

from app.core.config import settings
from app.core.security import AuthContext
from app.integrations.pdf_extractor import extract_text_from_pdf
from fastapi import HTTPException
from app.repositories.documents_repository import DocumentsRepository
from app.repositories.storage_repository import StorageRepository
from app.repositories.users_repository import UsersRepository
from app.services.indexing_service import IndexingService

logger = logging.getLogger(__name__)



def _validate_pdf(file_bytes: bytes, content_type: Optional[str]) -> None:
    """Valida MIME y magic-bytes de PDF + tamaño máximo (50 MB)."""
    if content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are allowed")
    max_size = 50 * 1024 * 1024  # 50 MB
    if len(file_bytes) > max_size:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    if not file_bytes[:4] == b"%PDF":
        raise HTTPException(status_code=400, detail="Invalid PDF file (magic bytes)")


class DocumentsService:
    def __init__(
        self,
        documents_repository: Optional[DocumentsRepository] = None,
        storage_repository: Optional[StorageRepository] = None,
        users_repository: Optional[UsersRepository] = None,
    ) -> None:
        self.documents_repository = documents_repository or DocumentsRepository()
        self.storage_repository = storage_repository or StorageRepository()
        self.users_repository = users_repository or UsersRepository()

    def upload_document(
        self,
        auth: AuthContext,
        file_bytes: bytes,
        filename: Optional[str],
        content_type: Optional[str],
        titulo: str,
        descripcion: Optional[str],
        categoria_id: Optional[int],
        codigo_documento: Optional[str],
    ) -> tuple[dict, dict]:
        self.users_repository.get_or_create_user(auth)
        if auth.institucion_id is None and not auth.is_platform_admin:
            raise HTTPException(status_code=403, detail="Institution membership required")
        # Validación de uploads (seguridad)
        _validate_pdf(file_bytes, content_type)
        # Validación de institución para categoría (FASE C)
        if categoria_id is not None:
            from app.repositories.categories_repository import CategoriesRepository
            cat_repo = CategoriesRepository()
            cat = cat_repo.get_by_id(categoria_id, auth.institucion_id)
            if not cat:
                raise HTTPException(status_code=403, detail="Category does not belong to institution")
        ext = os.path.splitext(filename or "")[1] or ".pdf"
        storage_path = f"{auth.institucion_id}/documents/{uuid.uuid4().hex}{ext}"
        ruta_archivo = self.storage_repository.upload_document(
            path=storage_path,
            content=file_bytes,
            content_type=content_type,
        )
        document = self.documents_repository.create_document(
            categoria_id=categoria_id,
            codigo_documento=codigo_documento,
            titulo=titulo,
            descripcion=descripcion,
            institucion_id=auth.institucion_id,
        )
        version = self.documents_repository.create_document_version(
            documento_id=document["id"],
            ruta_archivo=ruta_archivo,
            cargado_por_external_auth_id=auth.external_auth_id,
            original_filename=filename,
            mime_type=content_type,
            file_size_bytes=len(file_bytes),
        )
        self._index_or_extract(document["id"], version["id"], file_bytes, filename)
        return document, version

    def list_documents(self, auth: AuthContext) -> list[tuple[dict, Optional[dict]]]:
        institution_id = None if auth.is_platform_admin else auth.institucion_id
        documents = self.documents_repository.list_documents(institucion_id=institution_id)
        return [(document, _active_version(document.get("documento_versiones") or [])) for document in documents]

    def get_document(self, documento_id: int, auth: AuthContext) -> Optional[tuple[dict, list[dict]]]:
        document = self.documents_repository.get_document_by_id(documento_id, institucion_id=auth.institucion_id)
        if not document:
            return None
        versions = document.get("documento_versiones") or []
        return document, versions

    def deactivate_document(self, documento_id: int, auth: AuthContext) -> Optional[tuple[dict, Optional[dict]]]:
        doc = self.documents_repository.deactivate_document(documento_id, institucion_id=auth.institucion_id)
        if not doc:
            return None
        document = self.documents_repository.get_document_by_id(documento_id, institucion_id=auth.institucion_id)
        versions = document.get("documento_versiones") or [] if document else []
        return document, _active_version(versions)

    def upload_new_version(
        self,
        documento_id: int,
        auth: AuthContext,
        file_bytes: bytes,
        filename: Optional[str],
        content_type: Optional[str],
    ) -> tuple[dict, dict]:
        document = self.documents_repository.get_document_by_id(documento_id, institucion_id=auth.institucion_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        # Regla 404: si el documento pertenece a otra institución, no existe para este admin
        if document.get("institucion_id") != auth.institucion_id and not auth.is_platform_admin:
            raise HTTPException(status_code=404, detail="Document belongs to another institution")
        self.users_repository.get_or_create_user(auth)
        _validate_pdf(file_bytes, content_type)
        ext = os.path.splitext(filename or "")[1] or ".pdf"
        storage_path = f"{auth.institucion_id}/documents/{uuid.uuid4().hex}{ext}"
        ruta_archivo = self.storage_repository.upload_document(
            path=storage_path,
            content=file_bytes,
            content_type=content_type,
        )
        version = self.documents_repository.create_document_version(
            documento_id=documento_id,
            ruta_archivo=ruta_archivo,
            cargado_por_external_auth_id=auth.external_auth_id,
            original_filename=filename,
            mime_type=content_type,
            file_size_bytes=len(file_bytes),
        )
        self._index_or_extract(documento_id, version["id"], file_bytes, filename, institucion_id=auth.institucion_id)
        return document, version

    @staticmethod
    def _index_or_extract(
        documento_id: int,
        version_id: int,
        file_bytes: bytes,
        filename: Optional[str],
        institucion_id: Optional[int] = None,
    ) -> None:
        if not settings.embeddings_enabled:
            DocumentsService._extract_and_log(
                documento_id=documento_id,
                version_id=version_id,
                filename=filename,
                file_bytes=file_bytes,
            )
            return
        try:
            result = IndexingService().index_version(version_id, file_bytes=file_bytes, institucion_id=institucion_id)
        except Exception as exc:
            logger.warning(
                "Indexing failed unexpectedly documento_id=%s version_id=%s filename=%s error=%s",
                documento_id,
                version_id,
                filename,
                exc,
            )
            return
        if not result.ok:
            logger.warning(
                "Indexing error documento_id=%s version_id=%s filename=%s error=%s",
                documento_id,
                version_id,
                filename,
                result.error,
            )
        else:
            logger.info(
                "Indexing done documento_id=%s version_id=%s filename=%s status=%s total_chunks=%s total_tokens=%s model=%s elapsed_ms=%.1f",
                documento_id,
                version_id,
                filename,
                result.status,
                result.total_chunks,
                result.total_tokens,
                result.embedding_model,
                result.elapsed_ms,
            )

    @staticmethod
    def _extract_and_log(
        documento_id: int,
        version_id: int,
        file_bytes: bytes,
        filename: Optional[str],
    ) -> None:
        try:
            result = extract_text_from_pdf(file_bytes)
        except Exception as exc:
            logger.warning(
                "PDF extraction failed unexpectedly documento_id=%s version_id=%s filename=%s error=%s",
                documento_id,
                version_id,
                filename,
                exc,
            )
            return
        if not result.ok:
            logger.warning(
                "PDF extraction error documento_id=%s version_id=%s filename=%s error=%s",
                documento_id,
                version_id,
                filename,
                result.error,
            )
        elif result.total_chars == 0:
            logger.warning(
                "PDF has no extractable text (scanned/empty) documento_id=%s version_id=%s filename=%s page_count=%s",
                documento_id,
                version_id,
                filename,
                result.page_count,
            )
        else:
            preview = " ".join(page.text for page in result.pages[:1]).strip()
            logger.info(
                "PDF extracted documento_id=%s version_id=%s filename=%s page_count=%s total_chars=%s preview=%r",
                documento_id,
                version_id,
                filename,
                result.page_count,
                result.total_chars,
                preview[:200],
            )

    def reindex(self, documento_id: Optional[int], auth: AuthContext) -> int:
        institution_id = None if auth.is_platform_admin else auth.institucion_id
        versions = self.documents_repository.list_versions_for_reindex(documento_id, institucion_id=institution_id)
        updated = 0
        for version in versions:
            result = IndexingService().index_version(version["id"], institucion_id=institution_id)
            if result.ok:
                updated += 1
        return updated


def _active_version(versions: list[dict]) -> Optional[dict]:
    active = [version for version in versions if version.get("es_version_activa")]
    if active:
        return sorted(active, key=lambda version: version["numero_version"], reverse=True)[0]
    if not versions:
        return None
    return sorted(versions, key=lambda version: version["numero_version"], reverse=True)[0]

