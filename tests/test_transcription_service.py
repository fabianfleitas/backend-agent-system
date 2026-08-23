from __future__ import annotations

from typing import List, Optional

from app.integrations.stt_client import STTResponse
from app.services.transcription_service import TranscriptionService


class FakeSTTClient:
    def __init__(
        self,
        text: str = "¿Cuáles son los requisitos para matricularme?",
        model: str = "fake-whisper",
        duration: Optional[float] = 2.5,
        fail_with: Optional[Exception] = None,
    ) -> None:
        self.text = text
        self.model = model
        self.duration = duration
        self.fail_with = fail_with
        self.calls: List[tuple] = []

    def transcribe(self, audio_bytes: bytes, filename: str, content_type: Optional[str]) -> STTResponse:
        self.calls.append((audio_bytes, filename, content_type))
        if self.fail_with is not None:
            return STTResponse(text="", model=self.model, duration=None, ok=False, error=str(self.fail_with))
        return STTResponse(text=self.text, model=self.model, duration=self.duration)


def _make_service(client: Optional[FakeSTTClient] = None) -> tuple[TranscriptionService, FakeSTTClient]:
    fake = client or FakeSTTClient()
    service = TranscriptionService(client=fake, model="fake-whisper")
    return service, fake


def test_transcribe_returns_text_and_duration() -> None:
    service, fake = _make_service()
    result = service.transcribe(b"RIFF-data", "voice.wav", "audio/wav")
    assert result.ok
    assert result.error is None
    assert result.text == "¿Cuáles son los requisitos para matricularme?"
    assert result.model == "fake-whisper"
    assert result.duration == 2.5
    assert result.elapsed_ms >= 0
    assert fake.calls == [(b"RIFF-data", "voice.wav", "audio/wav")]


def test_transcribe_empty_audio_fails_without_calling_client() -> None:
    client = FakeSTTClient()
    service = TranscriptionService(client=client, model="fake-whisper")
    result = service.transcribe(b"", "voice.wav", "audio/wav")
    assert not result.ok
    assert result.error == "empty audio"
    assert result.text == ""
    assert client.calls == []


def test_transcribe_client_failure_sets_not_ok() -> None:
    service, _ = _make_service(FakeSTTClient(fail_with=RuntimeError("provider down")))
    result = service.transcribe(b"RIFF-data", "voice.wav", "audio/wav")
    assert not result.ok
    assert result.error == "provider down"
    assert result.text == ""
    assert result.duration is None