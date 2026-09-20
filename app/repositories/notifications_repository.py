from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class NotificationsRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def get_by_idempotency(self, clave_idempotencia: str) -> Optional[dict]:
        resp = (
            self.client.table("notificaciones")
            .select("*")
            .eq("clave_idempotencia", clave_idempotencia)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def create(self, payload: dict) -> dict:
        resp = self.client.table("notificaciones").insert(payload).execute()
        return resp.data[0]

    def mark_sent(self, notification_id: int, fecha_envio: str) -> Optional[dict]:
        resp = (
            self.client.table("notificaciones")
            .update({"estado": "SENT", "fecha_envio": fecha_envio})
            .eq("id", notification_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def mark_failed(self, notification_id: int, error: str) -> Optional[dict]:
        resp = (
            self.client.table("notificaciones")
            .update({"estado": "FAILED", "error": error[:500]})
            .eq("id", notification_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def list_by_institution(self, institucion_id: int) -> list[dict]:
        resp = (
            self.client.table("notificaciones")
            .select("*")
            .eq("institucion_id", institucion_id)
            .order("created_at", desc=True)
            .execute()
        )
        return list(resp.data or [])