from __future__ import annotations

from typing import Optional

from app.integrations.tts_client import TTSResponse
from app.services.synthesis_service import SynthesisService


class FakeTTSClient:
    def __init__(
        self,
        audio_bytes: bytes = b"ID3-mp3-bytes",
        model: str = "fake-tts",
        fail_with: Optional[Exception] = None,
    ) -> None:
        self.audio_bytes = audio_bytes
        self.model = model
        self.fail_with = fail_with
        self.calls: list[str] = []

    def synthesize(self, text: str) -> TTSResponse:
        self.calls.append(text)
        if self.fail_with is not None:
            return TTSResponse(audio_bytes=b"", model=self.model, content_type="audio/wav", ok=False, error=str(self.fail_with))
        return TTSResponse(audio_bytes=self.audio_bytes, model=self.model, content_type="audio/mpeg")


def _make_service(client: Optional[FakeTTSClient] = None) -> tuple[SynthesisService, FakeTTSClient]:
    fake = client or FakeTTSClient()
    service = SynthesisService(client=fake, model="fake-tts")
    return service, fake


def test_synthesize_returns_audio() -> None:
    service, fake = _make_service()
    result = service.synthesize("Los requisitos para la matrícula son los siguientes.")
    assert result.ok
    assert result.error is None
    assert result.audio_bytes == b"ID3-mp3-bytes"
    assert result.content_type == "audio/mpeg"
    assert result.model == "fake-tts"
    assert result.elapsed_ms >= 0


def test_synthesize_empty_text_fails_without_calling_client() -> None:
    fake = FakeTTSClient()
    service = SynthesisService(client=fake, model="fake-tts")
    for blank in ("", "   "):
        result = service.synthesize(blank)
        assert not result.ok
        assert result.error == "empty text"
        assert result.audio_bytes == b""
    assert fake.calls == []


def test_synthesize_client_failure_sets_not_ok() -> None:
    service, _ = _make_service(FakeTTSClient(fail_with=RuntimeError("provider down")))
    result = service.synthesize("texto a sintetizar")
    assert not result.ok
    assert result.error == "provider down"
    assert result.audio_bytes == b""
    assert result.content_type == "audio/wav"


def test_synthesize_truncates_long_text(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "tts_max_input_chars", 10)
    service, fake = _make_service()
    service.synthesize("12345678901234567890")
    assert fake.calls == ["1234567890"]