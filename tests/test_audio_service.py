from __future__ import annotations

import pytest

from app.core.security import AuthContext
from app.services.audio_service import AudioService


class FakeAudioRepository:
    def __init__(self, interaction=None) -> None:
        self.interaction = interaction
        self.created = []

    def create_audio_interaction(self, **kwargs):
        self.created.append(kwargs)
        return {"id": 1, **kwargs}

    def get_audio_interaction(self, audio_interaction_id: int):
        if self.interaction and self.interaction.get("id") == audio_interaction_id:
            return self.interaction
        return None


class FakeStorageRepository:
    def __init__(self, files=None) -> None:
        self.files = files or {}
        self.uploaded = []

    def upload_audio(self, path: str, content: bytes, content_type=None, upsert=False):
        self.uploaded.append((path, content, content_type))
        self.files[path] = content
        return path

    def download_audio(self, path: str) -> bytes:
        return self.files.get(path, b"")


class FakeUsersRepository:
    def get_or_create_user(self, auth: AuthContext):
        return {"id": 1, "external_auth_id": auth.external_auth_id}


def test_audio_service_get_response_audio_success() -> None:
    interaction = {
        "id": 1,
        "external_auth_id": "student-1",
        "ruta_audio_respuesta": "audio/resp.mp3",
    }
    storage = FakeStorageRepository({"audio/resp.mp3": b"MP3-DATA"})
    repo = FakeAudioRepository(interaction)
    service = AudioService(audio_repository=repo, storage_repository=storage, users_repository=FakeUsersRepository())

    auth = AuthContext(external_auth_id="student-1", tipo_usuario="ESTUDIANTE", correo=None, auth_provider="delegated")
    result = service.get_response_audio(1, auth)
    assert result is not None
    data, content_type = result
    assert data == b"MP3-DATA"
    assert content_type == "audio/mpeg"


def test_audio_service_get_response_audio_admin_access() -> None:
    interaction = {
        "id": 1,
        "external_auth_id": "student-1",
        "ruta_audio_respuesta": "audio/resp.wav",
    }
    storage = FakeStorageRepository({"audio/resp.wav": b"WAV-DATA"})
    repo = FakeAudioRepository(interaction)
    service = AudioService(audio_repository=repo, storage_repository=storage, users_repository=FakeUsersRepository())

    admin_auth = AuthContext(external_auth_id="admin-9", tipo_usuario="ADMIN", correo=None, auth_provider="delegated")
    result = service.get_response_audio(1, admin_auth)
    assert result is not None
    data, content_type = result
    assert data == b"WAV-DATA"
    assert content_type == "audio/wav"


def test_audio_service_get_response_audio_isolation_forbidden() -> None:
    interaction = {
        "id": 1,
        "external_auth_id": "student-1",
        "ruta_audio_respuesta": "audio/resp.mp3",
    }
    storage = FakeStorageRepository({"audio/resp.mp3": b"MP3-DATA"})
    repo = FakeAudioRepository(interaction)
    service = AudioService(audio_repository=repo, storage_repository=storage, users_repository=FakeUsersRepository())

    other_auth = AuthContext(external_auth_id="student-2", tipo_usuario="ESTUDIANTE", correo=None, auth_provider="delegated")
    with pytest.raises(PermissionError):
        service.get_response_audio(1, other_auth)


def test_audio_service_get_response_audio_not_found() -> None:
    repo = FakeAudioRepository(None)
    service = AudioService(audio_repository=repo, storage_repository=FakeStorageRepository(), users_repository=FakeUsersRepository())

    auth = AuthContext(external_auth_id="student-1", tipo_usuario="ESTUDIANTE", correo=None, auth_provider="delegated")
    assert service.get_response_audio(999, auth) is None
