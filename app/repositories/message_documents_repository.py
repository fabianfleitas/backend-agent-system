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