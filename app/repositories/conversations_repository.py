from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.supabase import get_supabase_client


class ConversationsRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def create_conversation(self, external_auth_id: str, title: str, institucion_id: int) -> dict:
        now = _utc_now_iso()
        response = (
            self.client.table("conversaciones")
            .insert({"external_auth_id": external_auth_id, "title": title, "last_interaction": now, "institucion_id": institucion_id})
            .execute()
        )
        return response.data[0]

    def get_conversation(self, conversation_id: int, institucion_id: Optional[int] = None) -> Optional[dict]:
        query = self.client.table("conversaciones").select("*").eq("id", conversation_id).limit(1)
        if institucion_id is not None:
            query = query.eq("institucion_id", institucion_id)
        response = query.execute()
        return response.data[0] if response.data else None

    def list_conversations(self, external_auth_id: str, include_hidden: bool, institucion_id: int) -> list[dict]:
        query = (
            self.client.table("conversaciones")
            .select("*")
            .eq("external_auth_id", external_auth_id)
            .eq("institucion_id", institucion_id)
        )
        if not include_hidden:
            query = query.eq("hidden", False)
        response = query.order("last_interaction", desc=True).execute()
        return list(response.data or [])

    def hide_conversation(self, external_auth_id: str, conversation_id: int, institucion_id: int) -> Optional[dict]:
        now = _utc_now_iso()
        response = (
            self.client.table("conversaciones")
            .update({"hidden": True, "last_interaction": now})
            .eq("id", conversation_id)
            .eq("external_auth_id", external_auth_id)
            .eq("institucion_id", institucion_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def touch_conversation(self, conversation_id: int) -> None:
        now = _utc_now_iso()
        (
            self.client.table("conversaciones")
            .update({"last_interaction": now})
            .eq("id", conversation_id)
            .execute()
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
