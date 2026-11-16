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
        pregunta_anonimizada: Optional[str] = None,
        observaciones: Optional[str] = None,
        embedding_model: Optional[str] = None,
        institucion_id: Optional[int] = None,
        score_fidelidad: Optional[float] = None,
        score_relevancia: Optional[float] = None,
        score_contexto: Optional[float] = None,
    ) -> dict:
        response = (
            self.client.table("audit_logs")
            .insert({
                "conversacion_id": conversation_id,
                "mensaje_id": message_id,
                "external_auth_id": external_auth_id,
                "pregunta_original": pregunta_original,
                "pregunta_anonimizada": pregunta_anonimizada,
                "respuesta_texto": respuesta_texto,
                "proveedor_ia": proveedor_ia,
                "modelo_ia": modelo_ia,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "tiempo_respuesta_ms": _milliseconds_as_int(tiempo_respuesta_ms),
                "observaciones": observaciones,
                "embedding_model": embedding_model,
                "institucion_id": institucion_id,
                "score_fidelidad": score_fidelidad,
                "score_relevancia": score_relevancia,
                "score_contexto": score_contexto,
            })
            .execute()
        )
        return response.data[0]

    def list_audit_logs(self, institucion_id: Optional[int] = None) -> list[dict]:
        query = self.client.table("audit_logs").select("*").order("fecha_evaluacion", desc=True)
        if institucion_id is not None:
            query = query.eq("institucion_id", institucion_id)
        response = query.execute()
        return list(response.data or [])

    def get_by_id(self, audit_id: str) -> Optional[dict]:
        resp = (
            self.client.table("audit_logs")
            .select("*")
            .eq("id", audit_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def update_observaciones(self, audit_id: str, observaciones: str) -> Optional[dict]:
        response = (
            self.client.table("audit_logs")
            .update({"observaciones": observaciones})
            .eq("id", audit_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def log_action(
        self,
        action: str,
        *,
        external_auth_id: Optional[str],
        institucion_id: Optional[int] = None,
        detalle: Optional[str] = None,
    ) -> Optional[dict]:
        """Registra una acción administrativa de gestión en `audit_logs`.

        `conversacion_id`/`mensaje_id` quedan NULL (acciones no vinculadas a un
        turno de chat). `action` es el tipo (DOC_UPLOAD, CATEGORY_CREATE, ...) y
        `detalle` va en observaciones.
        """
        response = (
            self.client.table("audit_logs")
            .insert({
                "conversacion_id": None,
                "mensaje_id": None,
                "external_auth_id": external_auth_id,
                "respuesta_texto": action,
                "proveedor_ia": None,
                "modelo_ia": None,
                "tokens_input": None,
                "tokens_output": None,
                "tiempo_respuesta_ms": None,
                "observaciones": detalle,
                "embedding_model": None,
                "institucion_id": institucion_id,
            })
            .execute()
        )
        return response.data[0] if response.data else None


def _milliseconds_as_int(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return int(round(value))
