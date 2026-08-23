from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class AudioRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def create_audio_interaction(
        self,
        conversation_id: int,
        message_id: int,
        external_auth_id: str,
        ruta_audio_original: str,
        ruta_audio_respuesta: Optional[str],
        transcripcion: Optional[str],
        formato_audio: Optional[str],
        tamano_bytes: Optional[int],
        duracion_segundos: Optional[float] = None,
        transcription_model: Optional[str] = None,
    ) -> dict:
        response = (
            self.client.table("audio_interactions")
            .insert(
                {
                    "conversacion_id": conversation_id,
                    "mensaje_id": message_id,
                    "external_auth_id": external_auth_id,
                    "ruta_audio_original": ruta_audio_original,
                    "ruta_audio_respuesta": ruta_audio_respuesta,
                    "transcripcion": transcripcion,
                    "transcription_model": transcription_model,
                    "duracion_segundos": duracion_segundos,
                    "formato_audio": formato_audio,
                    "tamano_bytes": tamano_bytes,
                }
            )
            .execute()
        )
        return response.data[0]

    def get_audio_interaction(self, audio_interaction_id: int) -> Optional[dict]:
        response = (
            self.client.table("audio_interactions")
            .select("*")
            .eq("id", audio_interaction_id)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]
        return None

