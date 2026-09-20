from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from app.core.supabase import get_supabase_client


class PiiRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def insert_mappings(self, rows: List[dict]) -> List[dict]:
        if not rows:
            return []
        response = self.client.table("pii_mappings").insert(rows).execute()
        return list(response.data or [])

    def list_expired(self, before: Optional[datetime] = None) -> List[dict]:
        cutoff = before or datetime.now(timezone.utc)
        response = (
            self.client.table("pii_mappings")
            .select("id")
            .lt("expires_at", cutoff.isoformat())
            .execute()
        )
        return list(response.data or [])

    def purge_expired(self, before: Optional[datetime] = None) -> int:
        cutoff = before or datetime.now(timezone.utc)
        response = (
            self.client.table("pii_mappings")
            .delete()
            .lt("expires_at", cutoff.isoformat())
            .execute()
        )
        return len(response.data or [])