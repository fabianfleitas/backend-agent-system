from __future__ import annotations

from typing import Any, List, Optional

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
        institucion_id: int,
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
                    "institucion_id": institucion_id,
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

    def get_document_by_id(self, documento_id: int, institucion_id: Optional[int] = None) -> Optional[dict]:
        query = self.client.table("documentos").select("*, documento_versiones(*)").eq("id", documento_id).limit(1)
        if institucion_id is not None:
            query = query.eq("institucion_id", institucion_id)
        response = query.execute()
        return response.data[0] if response.data else None

    def get_version_by_id(self, version_id: int, institucion_id: Optional[int] = None) -> Optional[dict]:
        query = (
            self.client.table("documento_versiones")
            .select("*, documentos!inner(institucion_id)")
            .eq("id", version_id)
            .limit(1)
        )
        if institucion_id is not None:
            query = query.eq("documentos.institucion_id", institucion_id)
        response = query.execute()
        return response.data[0] if response.data else None

    def update_version(self, version_id: int, institucion_id: Optional[int] = None, **fields: Any) -> Optional[dict]:
        query = (
            self.client.table("documento_versiones")
            .update(fields)
            .eq("id", version_id)
        )
        if institucion_id is not None:
            # Verificar pertenencia institucional antes de actualizar
            version = self.get_version_by_id(version_id, institucion_id)
            if version is None:
                return None
        response = query.execute()
        return response.data[0] if response.data else None

    def list_versions_for_reindex(self, documento_id: Optional[int], institucion_id: Optional[int] = None) -> List[dict]:
        if documento_id is not None:
            query = (
                self.client.table("documento_versiones")
                .select("*, documentos!inner(institucion_id)")
                .eq("documento_id", documento_id)
                .eq("es_version_activa", True)
            )
            if institucion_id is not None:
                query = query.eq("documentos.institucion_id", institucion_id)
            response = query.execute()
            return list(response.data or [])
        else:
            # Reindex global: solo cuando no se requiere aislamiento (platform admin)
            if institucion_id is not None:
                return []  # No permitido reindex sin documento específico para una institución
            query = (
                self.client.table("documento_versiones")
                .select("*, documentos!inner(institucion_id)")
                .in_("status", ["PENDING", "FAILED"])
                .eq("es_version_activa", True)
            )
            response = query.execute()
            return list(response.data or [])

    def deactivate_document(self, documento_id: int, institucion_id: Optional[int] = None) -> Optional[dict]:
        query = self.client.table("documentos").update({"activo": False}).eq("id", documento_id).eq("activo", True)
        if institucion_id is not None:
            query = query.eq("institucion_id", institucion_id)
        response = query.execute()
        return response.data[0] if response.data else None

    def list_documents(self, institucion_id: Optional[int] = None) -> list[dict]:
        query = self.client.table("documentos").select("*, documento_versiones(*)").order("fecha_creacion", desc=True)
        if institucion_id is not None:
            query = query.eq("institucion_id", institucion_id)
        response = query.execute()
        return list(response.data or [])

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
