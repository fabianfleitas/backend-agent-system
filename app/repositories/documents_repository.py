from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings
from app.core.supabase import get_supabase_client


class DocumentsRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def create_document(
        self,
        categoria_id: Optional[int],
        codigo_documento: Optional[str],
        titulo: str,
        descripcion: Optional[str],
    ) -> dict:
        response = (
            self.client.table("documentos")
            .insert(
                {
                    "categoria_id": categoria_id,
                    "codigo_documento": codigo_documento,
                    "titulo": titulo,
                    "descripcion": descripcion,
                    "activo": True,
                }
            )
            .execute()
        )
        return response.data[0]

    def create_document_version(
        self,
        documento_id: int,
        ruta_archivo: str,
        cargado_por_external_auth_id: str,
        original_filename: Optional[str],
        mime_type: Optional[str],
        file_size_bytes: int,
    ) -> dict:
        next_version = self._next_version_number(documento_id)
        if next_version > 1:
            self._deactivate_versions(documento_id)
        response = (
            self.client.table("documento_versiones")
            .insert(
                {
                    "documento_id": documento_id,
                    "numero_version": next_version,
                    "ruta_archivo": ruta_archivo,
                    "storage_bucket": settings.supabase_storage_bucket_documents,
                    "original_filename": original_filename,
                    "mime_type": mime_type or "application/pdf",
                    "file_size_bytes": file_size_bytes,
                    "status": "PENDING",
                    "es_version_activa": True,
                    "cargado_por_external_auth_id": cargado_por_external_auth_id,
                }
            )
            .execute()
        )
        return response.data[0]

    def list_documents(self) -> list[dict]:
        response = (
            self.client.table("documentos")
            .select("*, documento_versiones(*)")
            .order("fecha_creacion", desc=True)
            .execute()
        )
        return list(response.data or [])

    def reindex_versions(self, documento_id: Optional[int]) -> int:
        query = self.client.table("documento_versiones").update(
            {
                "status": "READY",
                "total_chunks": 0,
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if documento_id is not None:
            query = query.eq("documento_id", documento_id)
        response = query.execute()
        return len(response.data or [])

    def _next_version_number(self, documento_id: int) -> int:
        response = (
            self.client.table("documento_versiones")
            .select("numero_version")
            .eq("documento_id", documento_id)
            .order("numero_version", desc=True)
            .limit(1)
            .execute()
        )
        if not response.data:
            return 1
        return int(response.data[0]["numero_version"]) + 1

    def _deactivate_versions(self, documento_id: int) -> None:
        (
            self.client.table("documento_versiones")
            .update({"es_version_activa": False})
            .eq("documento_id", documento_id)
            .execute()
        )
