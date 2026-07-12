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
    ) -> dict:
        self.users_repository.get_or_create_user(auth)
        source_ext = os.path.splitext(source_filename or "")[1] or ".bin"
        original_path = f"audio/{uuid.uuid4().hex}{source_ext}"
        response_path = f"audio/{uuid.uuid4().hex}.wav"
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
            formato_audio=source_content_type,
            tamano_bytes=len(audio_bytes),
            duracion_segundos=None,
        )

