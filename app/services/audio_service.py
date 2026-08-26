from __future__ import annotations

import os
import uuid
from typing import Optional

from app.core.security import AuthContext
from app.repositories.audio_repository import AudioRepository
from app.repositories.storage_repository import StorageRepository
from app.repositories.users_repository import UsersRepository


class AudioService:
    def __init__(
        self,
        audio_repository: Optional[AudioRepository] = None,
        storage_repository: Optional[StorageRepository] = None,
        users_repository: Optional[UsersRepository] = None,
    ) -> None:
        self.audio_repository = audio_repository or AudioRepository()
        self.storage_repository = storage_repository or StorageRepository()
        self.users_repository = users_repository or UsersRepository()

    def create_audio_interaction(
        self,
        auth: AuthContext,
        conversation_id: int,
        message_id: int,
        audio_bytes: bytes,
        source_filename: Optional[str],
        source_content_type: Optional[str],
        transcription: Optional[str],
        response_audio_bytes: bytes = b"",
        response_content_type: str = "audio/wav",
        transcription_model: Optional[str] = None,
        duracion_segundos: Optional[float] = None,
    ) -> dict:
        self.users_repository.get_or_create_user(auth)
        source_ext = os.path.splitext(source_filename or "")[1] or ".bin"
        original_path = f"{auth.institucion_id}/audio/{uuid.uuid4().hex}{source_ext}"
        response_ext = _audio_extension(response_content_type)
        response_path = f"{auth.institucion_id}/audio/{uuid.uuid4().hex}{response_ext}"
        self.storage_repository.upload_audio(
            path=original_path,
            content=audio_bytes,
            content_type=source_content_type,
        )
        self.storage_repository.upload_audio(
            path=response_path,
            content=response_audio_bytes,
            content_type=response_content_type,
        )
        return self.audio_repository.create_audio_interaction(
            conversation_id=conversation_id,
            message_id=message_id,
            external_auth_id=auth.external_auth_id,
            ruta_audio_original=original_path,
            ruta_audio_respuesta=response_path,
            transcripcion=transcription,
            transcription_model=transcription_model,
            formato_audio=source_content_type,
            tamano_bytes=len(audio_bytes),
            duracion_segundos=duracion_segundos,
            institucion_id=auth.institucion_id,
        )

    def get_audio_interaction(self, audio_interaction_id: int) -> Optional[dict]:
        return self.audio_repository.get_audio_interaction(audio_interaction_id)

    def get_response_audio(
        self,
        audio_interaction_id: int,
        auth: AuthContext,
    ) -> Optional[tuple[bytes, str]]:
        interaction = self.audio_repository.get_audio_interaction(
            audio_interaction_id, institucion_id=auth.institucion_id
        )
        if not interaction:
            # Intento de acceso a recurso de otra institución → 404
            # Verificar si existe con cualquier institución para distinguir 404 vs 403 es opcional;
            # aquí simplificamos: si no aparece con la institución del auth, es 404 (regla cruzado)
            return None
        # Regla 404/403: si institución no coincide y no es superadmin → 404
        # Si institución coincide pero otro usuario → 403 (PermissionError)
        if auth.institucion_id is not None and interaction.get("institucion_id") != auth.institucion_id and not auth.is_platform_admin:
            return None  # 404 acceso cruzado
        is_admin_same_inst = (
            auth.tipo_miembro in ("ADMIN", "SECRETARIA")
            and auth.institucion_id is not None
            and interaction.get("institucion_id") == auth.institucion_id
        )
        if interaction.get("external_auth_id") != auth.external_auth_id and not auth.is_platform_admin and not is_admin_same_inst:
            raise PermissionError("No autorizado para acceder a este audio")
        response_path = interaction.get("ruta_audio_respuesta")
        if not response_path:
            return None
        try:
            audio_bytes = self.storage_repository.download_audio(response_path)
        except Exception:
            return None
        if not audio_bytes:
            return None
        content_type = _content_type_from_path(response_path)
        return audio_bytes, content_type


def _content_type_from_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    mapping = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".pcm": "audio/pcm",
        ".ogg": "audio/ogg",
        ".aac": "audio/aac",
    }
    return mapping.get(ext, "audio/mpeg")


def _audio_extension(content_type: Optional[str]) -> str:
    mapping = {
        "audio/mpeg": ".mp3",
        "audio/pcm": ".pcm",
        "audio/wav": ".wav",
        "audio/ogg": ".ogg",
        "audio/aac": ".aac",
    }
    return mapping.get(content_type or "", ".wav")

