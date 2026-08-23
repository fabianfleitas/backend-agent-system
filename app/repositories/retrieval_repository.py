from __future__ import annotations

from typing import Any, List, Optional

from app.core.supabase import get_supabase_client
from app.repositories.embeddings_repository import vector_to_pgstring


class RetrievalRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def match_chunks(
        self,
        query_embedding: List[float],
        match_count: int,
        similarity_threshold: float,
    ) -> List[dict]:
        response = (
            self.client.rpc(
                "match_document_chunks",
                {
                    "query_embedding": vector_to_pgstring(query_embedding),
                    "match_count": match_count,
                    "similarity_threshold": similarity_threshold,
                },
            )
            .execute()
        )
        return list(response.data or [])