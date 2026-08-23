from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.integrations.tts_client import OpenAICompatibleTTSClient, TTSClient

logger = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    audio_bytes: bytes
    content_type: str
    model: str
    elapsed_ms: float = 0.0
    ok: bool = True
    error: Optional[str] = None


class SynthesisService:
    def __init__(
        self,
        client: Optional[TTSClient] = None,
        model: Optional[str] = None,
    ) -> None:
        self.client = client or OpenAICompatibleTTSClient(
            api_key=settings.openrouter_api_key or "",
            model=settings.tts_model,
            base_url=settings.openrouter_base_url,
            voice=settings.tts_voice,
            response_format=settings.tts_response_format,
            timeout=settings.tts_request_timeout,
            max_retries=settings.tts_max_retries,
        )
        self.model = model or settings.tts_model

    def synthesize(self, text: str) -> SynthesisResult:
        if not text or not text.strip():
            return SynthesisResult(
                audio_bytes=b"",
                content_type="audio/wav",
                model=self.model,
                ok=False,
                error="empty text",
            )
        clamped = text[: settings.tts_max_input_chars]
        response = self.client.synthesize(clamped)
        if not response.ok:
            logger.error(
                "TTS failed model=%s error=%s elapsed_ms=%.1f",
                self.model,
                response.error,
                response.elapsed_ms,
            )
            return SynthesisResult(
                audio_bytes=b"",
                content_type="audio/wav",
                model=self.model,
                elapsed_ms=response.elapsed_ms,
                ok=False,
                error=response.error,
            )
        return SynthesisResult(
            audio_bytes=response.audio_bytes,
            content_type=response.content_type,
            model=response.model,
            elapsed_ms=response.elapsed_ms,
            ok=True,
        )