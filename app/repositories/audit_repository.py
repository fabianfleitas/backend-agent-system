from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class AuditRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def create_audit_log(
        self,
        conversation_id: int,
        message_id: int,
        external_auth_id: str,
        respuesta_texto: str,
        proveedor_ia: Optional[str],
        modelo_ia: Optional[str],
        tokens_input: Optional[int],
        tokens_output: Optional[int],
        tiempo_respuesta_ms: Optional[float],
        pregunta_original: Optional[str] = None,
        observaciones: Optional[str] = None,
    ) -> dict:
        response = (
            self.client.table("audit_logs")
            .insert(
                {
                    "conversacion_id": conversation_id,
                    "mensaje_id": message_id,
                    "external_auth_id": external_auth_id,
                    "pregunta_original": pregunta_original,
                    "respuesta_texto": respuesta_texto,
                    "proveedor_ia": proveedor_ia,
                    "modelo_ia": modelo_ia,
                    "tokens_input": tokens_input,
                    "tokens_output": tokens_output,
                    "tiempo_respuesta_ms": _milliseconds_as_int(tiempo_respuesta_ms),
                    "observaciones": observaciones,
                }
            )
            .execute()
        )
        return response.data[0]

    def list_audit_logs(self) -> list[dict]:
        response = (
            self.client.table("audit_logs")
            .select("*")
            .order("fecha_evaluacion", desc=True)
            .execute()
        )
        return list(response.data or [])


def _milliseconds_as_int(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return int(round(value))

