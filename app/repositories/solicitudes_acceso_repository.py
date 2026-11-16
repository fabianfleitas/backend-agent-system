from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class SolicitudesAccesoRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def create(self, payload: dict) -> dict:
        resp = self.client.table("solicitudes_acceso").insert(payload).execute()
        return resp.data[0]
