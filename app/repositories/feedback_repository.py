from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class FeedbackRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def create_feedback(
        self,
        message_id: int,
        rating: int,
        comment: Optional[str],
        audit_id: str,
        external_auth_id: str,
        institucion_id: int = None,
    ) -> dict:
        response = (
            self.client.table("feedback")
            .insert({
                "message_id": message_id,
                "rating": rating,
                "comment": comment,
                "audit_id": audit_id,
                "external_auth_id": external_auth_id,
                "institucion_id": institucion_id,
            })
            .execute()
        )
        return response.data[0]

    def list_feedback_by_institution(self, institucion_id: int) -> list[dict]:
        response = (
            self.client.table("feedback")
            .select("*")
            .eq("institucion_id", institucion_id)
            .execute()
        )
        return list(response.data or [])

    def get_feedback_by_message_ids(self, message_ids: list[int]) -> list[dict]:
        if not message_ids:
            return []
        response = (
            self.client.table("feedback")
            .select("message_id, rating, comment")
            .in_("message_id", message_ids)
            .execute()
        )
        return list(response.data or [])

    def list_feedback(
        self,
        institucion_id: int,
        conversacion_id: Optional[int] = None,
        message_id: Optional[int] = None,
        rating: Optional[int] = None,
        include_inactive: bool = False,
    ) -> list[dict]:
        query = (
            self.client.table("feedback")
            .select("*, mensajes!inner(conversacion_id, contenido_texto)")
            .eq("institucion_id", institucion_id)
        )
        if not include_inactive:
            query = query.eq("is_active", True)
        if message_id is not None:
            query = query.eq("message_id", message_id)
        if rating is not None:
            query = query.eq("rating", rating)
        if conversacion_id is not None:
            msg_resp = self.client.table("mensajes").select("id").eq("conversacion_id", conversacion_id).execute()
            ids = [m["id"] for m in (msg_resp.data or [])]
            if not ids:
                return []
            query = query.in_("message_id", ids)
        response = query.order("created_at", desc=True).execute()
        return list(response.data or [])

    def deactivate_feedback(self, feedback_id: int, institucion_id: int) -> Optional[dict]:
        response = (
            self.client.table("feedback")
            .update({"is_active": False})
            .eq("id", feedback_id)
            .eq("institucion_id", institucion_id)
            .execute()
        )
        return response.data[0] if response.data else None
