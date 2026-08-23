from __future__ import annotations

from typing import Any, List, Optional

from app.core.config import settings
from app.core.supabase import get_supabase_client


class ChunksRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def insert_chunks(self, version_id: int, rows: List[dict]) -> List[dict]:
        inserted: List[dict] = []
        batch_size = settings.indexing_insert_batch_size
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset : offset + batch_size]
            response = (
                self.client.table("document_chunks")
                .insert(batch)
                .execute()
            )
            inserted.extend(response.data or [])
        return inserted

    def delete_by_version(self, version_id: int) -> int:
        response = (
            self.client.table("document_chunks")
            .delete()
            .eq("documento_version_id", version_id)
            .execute()
        )
        return len(response.data or [])

    def list_by_version(self, version_id: int) -> List[dict]:
        response = (
            self.client.table("document_chunks")
            .select("*")
            .eq("documento_version_id", version_id)
            .order("chunk_index")
            .execute()
        )
        return list(response.data or [])