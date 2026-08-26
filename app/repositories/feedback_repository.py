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
