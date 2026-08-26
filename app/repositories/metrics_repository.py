from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class MetricsRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def list_messages(self, institucion_id: Optional[int] = None) -> list[dict]:
        # mensajes heredan institución vía conversacion_id
        # Para métricas simples filtramos por conversación de la institución
        if institucion_id is not None:
            conv_ids = (
                self.client.table("conversaciones")
                .select("id")
                .eq("institucion_id", institucion_id)
                .execute()
                .data
                or []
            )
            ids = [c["id"] for c in conv_ids]
            if not ids:
                return []
            resp = self.client.table("mensajes").select("*").in_("conversacion_id", ids).execute()
            return list(resp.data or [])
        resp = self.client.table("mensajes").select("*").execute()
        return list(resp.data or [])

    def list_conversations(self, institucion_id: Optional[int] = None) -> list[dict]:
        query = self.client.table("conversaciones").select("id")
        if institucion_id is not None:
            query = query.eq("institucion_id", institucion_id)
        resp = query.execute()
        return list(resp.data or [])

    def list_documents(self, institucion_id: Optional[int] = None) -> list[dict]:
        query = self.client.table("documentos").select("id")
        if institucion_id is not None:
            query = query.eq("institucion_id", institucion_id)
        resp = query.execute()
        return list(resp.data or [])

    def list_feedbacks(self, institucion_id: Optional[int] = None) -> list[dict]:
        query = self.client.table("feedback").select("id")
        if institucion_id is not None:
            query = query.eq("institucion_id", institucion_id)
        resp = query.execute()
        return list(resp.data or [])

    def list_audit_logs(self, institucion_id: Optional[int] = None) -> list[dict]:
        query = self.client.table("audit_logs").select("*")
        if institucion_id is not None:
            query = query.eq("institucion_id", institucion_id)
        resp = query.order("fecha_evaluacion", desc=True).execute()
        return list(resp.data or [])

    def list_message_documents(self, institucion_id: Optional[int] = None) -> list[dict]:
        # Join vía mensajes → conversaciones por institucion_id
        if institucion_id is not None:
            # Subconsulta de conversacion_ids para esta institución
            conv_resp = (
                self.client.table("conversaciones")
                .select("id")
                .eq("institucion_id", institucion_id)
                .execute()
            )
            conv_ids = [c["id"] for c in (conv_resp.data or [])]
            if not conv_ids:
                return []
            msg_resp = (
                self.client.table("mensajes")
                .select("id")
                .in_("conversacion_id", conv_ids)
                .execute()
            )
            msg_ids = [m["id"] for m in (msg_resp.data or [])]
            if not msg_ids:
                return []
            resp = (
                self.client.table("message_documents")
                .select("*")
                .in_("mensaje_id", msg_ids)
                .execute()
            )
            return list(resp.data or [])
        resp = self.client.table("message_documents").select("*").execute()
        return list(resp.data or [])
