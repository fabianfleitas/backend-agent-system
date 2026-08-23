from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.integrations.stt_client import OpenAICompatibleSTTClient, STTClient

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    model: str
    duration: Optional[float]
    elapsed_ms: float = 0.0
    ok: bool = True
    error: Optional[str] = None


class TranscriptionService:
    def __init__(
        self,
        client: Optional[STTClient] = None,
        model: Optional[str] = None,
    ) -> None:
        self.client = client or OpenAICompatibleSTTClient(
            api_key=settings.openrouter_api_key or "",
            model=settings.stt_model,
            base_url=settings.openrouter_base_url,
            response_format=settings.stt_response_format,
            timeout=settings.stt_request_timeout,
            max_retries=settings.stt_max_retries,
        )
        self.model = model or settings.stt_model

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: Optional[str] = None,
    ) -> TranscriptionResult:
        if not audio_bytes:
            return TranscriptionResult(
                text="",
                model=self.model,
                duration=None,
                ok=False,
                error="empty audio",
            )
        response = self.client.transcribe(audio_bytes, filename, content_type)
        if not response.ok:
            logger.error(
                "STT failed model=%s error=%s elapsed_ms=%.1f",
                self.model,
                response.error,
                response.elapsed_ms,
            )
            return TranscriptionResult(
                text="",
                model=self.model,
                duration=None,
                elapsed_ms=response.elapsed_ms,
                ok=False,
                error=response.error,
            )
        return TranscriptionResult(
            text=response.text,
            model=response.model,
            duration=response.duration,
            elapsed_ms=response.elapsed_ms,
            ok=True,
        )