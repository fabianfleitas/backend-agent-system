from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class StripeEventsRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def get_event(self, stripe_event_id: str) -> Optional[dict]:
        resp = (
            self.client.table("stripe_eventos")
            .select("*")
            .eq("stripe_event_id", stripe_event_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def create_event(self, stripe_event_id: str, tipo_evento: str, payload: dict, procesado: bool = False, error: Optional[str] = None) -> dict:
        resp = (
            self.client.table("stripe_eventos")
            .insert({
                "stripe_event_id": stripe_event_id,
                "tipo_evento": tipo_evento,
                "payload": payload,
                "procesado": procesado,
                "error": error,
            })
            .execute()
        )
        return resp.data[0]

    def mark_processed(self, stripe_event_id: str) -> Optional[dict]:
        from datetime import datetime, timezone
        resp = (
            self.client.table("stripe_eventos")
            .update({"procesado": True, "procesado_at": datetime.now(timezone.utc).isoformat(), "error": None})
            .eq("stripe_event_id", stripe_event_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def mark_failed(self, stripe_event_id: str, error: str) -> Optional[dict]:
        resp = (
            self.client.table("stripe_eventos")
            .update({"procesado": False, "error": error})
            .eq("stripe_event_id", stripe_event_id)
            .execute()
        )
        return resp.data[0] if resp.data else None
