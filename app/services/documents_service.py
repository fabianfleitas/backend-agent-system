from __future__ import annotations

import os
import uuid
from typing import Optional

from app.core.security import AuthContext
from app.repositories.documents_repository import DocumentsRepository
from app.repositories.storage_repository import StorageRepository
from app.repositories.users_repository import UsersRepository


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
        ext = os.path.splitext(filename or "")[1] or ".pdf"
        storage_path = f"documents/{uuid.uuid4().hex}{ext}"
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
        )
        version = self.documents_repository.create_document_version(
            documento_id=document["id"],
            ruta_archivo=ruta_archivo,
            cargado_por_external_auth_id=auth.external_auth_id,
            original_filename=filename,
            mime_type=content_type,
            file_size_bytes=len(file_bytes),
        )
        return document, version

    def list_documents(self) -> list[tuple[dict, Optional[dict]]]:
        documents = self.documents_repository.list_documents()
        return [(document, _active_version(document.get("documento_versiones") or [])) for document in documents]

    def get_document(self, documento_id: int) -> Optional[tuple[dict, list[dict]]]:
        document = self.documents_repository.get_document_by_id(documento_id)
        if not document:
            return None
        versions = document.get("documento_versiones") or []
        return document, versions

    def deactivate_document(self, documento_id: int) -> Optional[tuple[dict, Optional[dict]]]:
        doc = self.documents_repository.deactivate_document(documento_id)
        if not doc:
            return None
        document = self.documents_repository.get_document_by_id(documento_id)
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
        document = self.documents_repository.get_document_by_id(documento_id)
        if not document:
            raise ValueError("Document not found")
        self.users_repository.get_or_create_user(auth)
        ext = os.path.splitext(filename or "")[1] or ".pdf"
        storage_path = f"documents/{uuid.uuid4().hex}{ext}"
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
        return document, version

    def reindex(self, documento_id: Optional[int]) -> int:
        return self.documents_repository.reindex_versions(documento_id)


def _active_version(versions: list[dict]) -> Optional[dict]:
    active = [version for version in versions if version.get("es_version_activa")]
    if active:
        return sorted(active, key=lambda version: version["numero_version"], reverse=True)[0]
    if not versions:
        return None
    return sorted(versions, key=lambda version: version["numero_version"], reverse=True)[0]

