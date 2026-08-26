from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat import routes as chat_routes
from app.core.config import settings
from app.services.synthesis_service import SynthesisResult
from app.services.transcription_service import TranscriptionResult

AUDIT_ID = "123e4567-e89b-12d3-a456-426614174000"
FECHA = "2026-08-20T00:00:00Z"


class FakeChatService:
    def __init__(self, result=None) -> None:
        self.result = result

    def answer_voice_query(self, auth, conversation_id: int, transcription: str):
        if self.result is None:
            return None
        return self.result


class FakeAudioService:
    def __init__(self, response_audio=None, raise_permission=False) -> None:
        self.calls: list[dict] = []
        self.response_audio = response_audio
        self.raise_permission = raise_permission

    def create_audio_interaction(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "id": 1,
            "mensaje_id": kwargs["message_id"],
            "ruta_audio_original": "audio/original.wav",
            "ruta_audio_respuesta": "audio/response.wav",
            "transcripcion": kwargs.get("transcription"),
            "transcription_model": kwargs.get("transcription_model"),
            "duracion_segundos": kwargs.get("duracion_segundos"),
            "formato_audio": kwargs.get("source_content_type"),
            "tamano_bytes": kwargs.get("audio_bytes") and len(kwargs["audio_bytes"]),
            "fecha_creacion": FECHA,
        }

    def get_response_audio(self, audio_interaction_id: int, auth):
        if self.raise_permission:
            raise PermissionError("No autorizado")
        if self.response_audio is not None:
            return self.response_audio
        return None


class FakeTranscriptionService:
    def __init__(self, result: Optional[TranscriptionResult] = None) -> None:
        self.result = result

    def transcribe(self, audio_bytes, filename, content_type) -> TranscriptionResult:
        return self.result or TranscriptionResult(
            text="¿Cuáles son los requisitos para matricularme?",
            model="fake-whisper",
            duration=2.5,
        )


class FakeSynthesisService:
    def __init__(self, result: Optional[SynthesisResult] = None) -> None:
        self.result = result

    def synthesize(self, text: str) -> SynthesisResult:
        return self.result or SynthesisResult(
            audio_bytes=b"ID3-mp3-bytes",
            content_type="audio/mpeg",
            model="fake-tts",
        )


class FakeAuditRepository:
    def __init__(self) -> None:
        self.updates: list[tuple[str, str]] = []

    def update_observaciones(self, audit_id: str, observaciones: str) -> None:
        self.updates.append((audit_id, observaciones))


def _result(sources=None):
    class _R:
        conversation_id = 1
        response = "MOCK: respuesta simulada basada en reglamentos institucionales"
        sources = []
        user_message = {
            "id": 10,
            "conversacion_id": 1,
            "rol_mensaje": "USER",
            "contenido_texto": "¿Cuáles son los requisitos para matricularme?",
            "proveedor_ia": None,
            "modelo_ia": None,
            "temperatura": None,
            "tokens_input": None,
            "tokens_output": None,
            "tiempo_respuesta_ms": None,
            "fecha_envio": FECHA,
            "audit_id": None,
        }
        assistant_message = {
            "id": 11,
            "conversacion_id": 1,
            "rol_mensaje": "ASSISTANT",
            "contenido_texto": "MOCK: respuesta simulada",
            "proveedor_ia": "OpenRouter",
            "modelo_ia": "mock",
            "temperatura": 0.2,
            "tokens_input": 8,
            "tokens_output": 6,
            "tiempo_respuesta_ms": 0.0,
            "fecha_envio": FECHA,
            "audit_id": AUDIT_ID,
        }
        audit_log = {"id": AUDIT_ID, "observaciones": "LLM: OpenRouter (contexto RAG) [voice]"}

    _R.sources = sources if sources is not None else []
    return _R()


def _configure(chats, transcription, audio, synthesis=None, audit=None, auth_override=None) -> FastAPI:
    app = FastAPI()
    app.include_router(chat_routes.router, prefix="/api/chat")
    app.dependency_overrides[chat_routes._get_chat_service] = lambda: chats
    app.dependency_overrides[chat_routes._get_transcription_service] = lambda: transcription
    app.dependency_overrides[chat_routes._get_audio_service] = lambda: audio
    app.dependency_overrides[chat_routes._get_synthesis_service] = lambda: synthesis or FakeSynthesisService()
    app.dependency_overrides[chat_routes._get_audit_repository] = lambda: audit or FakeAuditRepository()
    if auth_override is not None:
        from app.core.security import get_auth_context
        app.dependency_overrides[get_auth_context] = lambda: auth_override
    else:
        from tests.conftest import make_auth
        from app.core.security import get_auth_context
        app.dependency_overrides[get_auth_context] = lambda: make_auth(external_auth_id="student-1", institucion_id=1, tipo_miembro="ESTUDIANTE")
    return app


def _client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _post(client: TestClient) -> None:
    return client.post(
        "/api/chat/voice",
        params={"conversation_id": 1},
        files={"audio": ("voice.wav", b"RIFF-data", "audio/wav")},
    )


def test_voice_with_stt_enabled_transcribes_and_persists(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", True)
    audio = FakeAudioService()
    app = _configure(FakeChatService(_result()), FakeTranscriptionService(), audio)
    resp = _post(_client(app))
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcription"] == "¿Cuáles son los requisitos para matricularme?"
    assert body["sources"] == []
    assert body["audio_interaction"]["transcription_model"] == "fake-whisper"
    assert body["audio_interaction"]["duracion_segundos"] == 2.5
    assert audio.calls[0]["transcription_model"] == "fake-whisper"
    assert audio.calls[0]["duracion_segundos"] == 2.5


def test_voice_with_stt_disabled_uses_mock(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", False)
    audio = FakeAudioService()
    app = _configure(FakeChatService(_result()), FakeTranscriptionService(), audio)
    resp = _post(_client(app))
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcription"] == "MOCK: transcripción simulada del audio"
    assert body["audio_interaction"]["transcription_model"] is None


def test_voice_stt_failure_returns_503(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", True)
    failing = FakeTranscriptionService(
        TranscriptionResult(text="", model="fake-whisper", duration=None, ok=False, error="provider down")
    )
    app = _configure(FakeChatService(_result()), failing, FakeAudioService())
    resp = _post(_client(app))
    assert resp.status_code == 503


def test_voice_conversation_not_found_404(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", True)
    app = _configure(FakeChatService(None), FakeTranscriptionService(), FakeAudioService())
    resp = _post(_client(app))
    assert resp.status_code == 404


def test_voice_maps_real_sources_from_chat_result(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", True)
    sources = [
        {"document_id": 7, "document": "Reglamento Academico.pdf", "page": 3, "similarity_score": 0.87},
        {"document_id": 7, "document": "Reglamento Academico.pdf", "page": 4, "similarity_score": 0.71},
    ]
    app = _configure(FakeChatService(_result(sources)), FakeTranscriptionService(), FakeAudioService())
    resp = _post(_client(app))
    assert resp.status_code == 200
    body = resp.json()
    assert body["sources"] == sources


def test_voice_tts_enabled_synthesizes_response_audio(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", True)
    monkeypatch.setattr(settings, "tts_enabled", True)
    audio = FakeAudioService()
    app = _configure(FakeChatService(_result()), FakeTranscriptionService(), audio)
    resp = _post(_client(app))
    assert resp.status_code == 200
    assert audio.calls[0]["response_audio_bytes"] == b"ID3-mp3-bytes"
    assert audio.calls[0]["response_content_type"] == "audio/mpeg"


def test_voice_tts_failure_graceful_and_audit_note(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", True)
    monkeypatch.setattr(settings, "tts_enabled", True)
    failing = FakeSynthesisService(
        SynthesisResult(audio_bytes=b"", content_type="audio/wav", model="fake-tts", ok=False, error="provider down")
    )
    audit = FakeAuditRepository()
    audio = FakeAudioService()
    app = _configure(FakeChatService(_result()), FakeTranscriptionService(), audio, synthesis=failing, audit=audit)
    resp = _post(_client(app))
    assert resp.status_code == 200
    assert audio.calls[0]["response_audio_bytes"] == b""
    assert audio.calls[0]["response_content_type"] == "audio/wav"
    assert len(audit.updates) == 1
    audit_id, obs = audit.updates[0]
    assert audit_id == AUDIT_ID
    assert obs.endswith("| TTS_FAILED: provider down")


def test_voice_tts_disabled_keeps_empty_audio(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", True)
    monkeypatch.setattr(settings, "tts_enabled", False)
    audio = FakeAudioService()
    app = _configure(FakeChatService(_result()), FakeTranscriptionService(), audio)
    resp = _post(_client(app))
    assert resp.status_code == 200
    assert audio.calls[0]["response_audio_bytes"] == b""
    assert audio.calls[0]["response_content_type"] == "audio/wav"


def test_get_audio_response_success() -> None:
    from tests.conftest import make_auth
    audio = FakeAudioService(response_audio=(b"ID3-mp3-bytes", "audio/mpeg"))
    app = _configure(FakeChatService(), FakeTranscriptionService(), audio, auth_override=make_auth(external_auth_id="student-1", institucion_id=1, tipo_miembro="ESTUDIANTE"))
    client = _client(app)
    resp = client.get(
        "/api/chat/audio/1",
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"ID3-mp3-bytes"


def test_get_audio_response_forbidden() -> None:
    from tests.conftest import make_auth
    audio = FakeAudioService(raise_permission=True)
    app = _configure(FakeChatService(), FakeTranscriptionService(), audio, auth_override=make_auth(external_auth_id="student-2", institucion_id=1, tipo_miembro="ESTUDIANTE"))
    client = _client(app)
    resp = client.get(
        "/api/chat/audio/1",
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "No autorizado para acceder a este audio"


def test_get_audio_response_not_found() -> None:
    from tests.conftest import make_auth
    audio = FakeAudioService(response_audio=None)
    app = _configure(FakeChatService(), FakeTranscriptionService(), audio, auth_override=make_auth(external_auth_id="student-1", institucion_id=1, tipo_miembro="ESTUDIANTE"))
    client = _client(app)
    resp = client.get(
        "/api/chat/audio/999",
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Audio no encontrado"