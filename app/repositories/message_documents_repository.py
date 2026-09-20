from __future__ import annotations

from typing import Any, List, Optional

from app.core.config import settings
from app.core.supabase import get_supabase_client


class MessageDocumentsRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def insert_message_documents(self, rows: List[dict]) -> List[dict]:
        inserted: List[dict] = []
        batch_size = settings.indexing_insert_batch_size
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset : offset + batch_size]
            response = (
                self.client.table("message_documents")
                .insert(batch)
                .execute()
            )
            inserted.extend(response.data or [])
        return inserted

    def get_sources_by_message_ids(self, message_ids: List[int]) -> List[dict]:
        if not message_ids:
            return []
        response = (
            self.client.table("message_documents")
            .select("*")
            .in_("mensaje_id", message_ids)
            .execute()
        )
        return list(response.data or [])

    def get_document_titles(self, document_ids: List[int]) -> dict[int, Optional[str]]:
        if not document_ids:
            return {}
        response = (
            self.client.table("documentos")
            .select("id, titulo")
            .in_("id", document_ids)
            .execute()
        )
        return {r.get("id"): r.get("titulo") for r in (response.data or [])}