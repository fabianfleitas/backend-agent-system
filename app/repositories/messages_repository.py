from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class MessagesRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def create_message(
        self,
        conversation_id: int,
        external_auth_id: str,
        role: str,
        content: str,
        proveedor_ia: Optional[str] = None,
        modelo_ia: Optional[str] = None,
        temperatura: Optional[float] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        tiempo_respuesta_ms: Optional[float] = None,
        audit_id: Optional[str] = None,
        contenido_anonimizado: Optional[str] = None,
    ) -> dict:
        response = (
            self.client.table("mensajes")
            .insert(
                {
                    "conversacion_id": conversation_id,
                    "external_auth_id": external_auth_id,
                    "rol_mensaje": role,
                    "contenido_texto": content,
                    "contenido_anonimizado": contenido_anonimizado,
                    "proveedor_ia": proveedor_ia,
                    "modelo_ia": modelo_ia,
                    "temperatura": temperatura,
                    "tokens_input": tokens_input,
                    "tokens_output": tokens_output,
                    "tiempo_respuesta_ms": _milliseconds_as_int(tiempo_respuesta_ms),
                    "audit_id": audit_id,
                }
            )
            .execute()
        )
        return response.data[0]

    def get_conversation_messages(self, conversation_id: int) -> list[dict]:
        response = (
            self.client.table("mensajes")
            .select("*")
            .eq("conversacion_id", conversation_id)
            .order("fecha_envio")
            .execute()
        )
        return list(response.data or [])

    def get_message(self, message_id: int) -> Optional[dict]:
        response = (
            self.client.table("mensajes")
            .select("*")
            .eq("id", message_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def count_conversation_messages(self, conversation_id: int) -> int:
        response = (
            self.client.table("mensajes")
            .select("id")
            .eq("conversacion_id", conversation_id)
            .execute()
        )
        return len(response.data or [])

    def update_message_audit_id(self, message_id: int, audit_id: str) -> Optional[dict]:
        response = (
            self.client.table("mensajes")
            .update({"audit_id": audit_id})
            .eq("id", message_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def update_message(self, message_id: int, **fields) -> Optional[dict]:
        response = (
            self.client.table("mensajes")
            .update(fields)
            .eq("id", message_id)
            .execute()
        )
        return response.data[0] if response.data else None


def _milliseconds_as_int(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return int(round(value))
