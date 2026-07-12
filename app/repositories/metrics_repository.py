from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class MetricsRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def list_messages(self) -> list[dict]:
        response = self.client.table("mensajes").select("*").execute()
        return list(response.data or [])

    def list_conversations(self) -> list[dict]:
        response = self.client.table("conversaciones").select("id").execute()
        return list(response.data or [])

    def list_documents(self) -> list[dict]:
        response = self.client.table("documentos").select("id").execute()
        return list(response.data or [])

    def list_feedbacks(self) -> list[dict]:
        response = self.client.table("feedback").select("id").execute()
        return list(response.data or [])

    def list_audit_logs(self) -> list[dict]:
        response = self.client.table("audit_logs").select("*").execute()
        return list(response.data or [])

