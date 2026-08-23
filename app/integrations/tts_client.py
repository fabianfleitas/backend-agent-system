from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class TTSResponse:
    audio_bytes: bytes
    model: str
    content_type: str
    elapsed_ms: float = 0.0
    ok: bool = True
    error: Optional[str] = None


class TTSClient(Protocol):
    def synthesize(self, text: str) -> TTSResponse: ...


class OpenAICompatibleTTSClient:
    _CONTENT_TYPES = {
        "mp3": "audio/mpeg",
        "pcm": "audio/pcm",
        "wav": "audio/wav",
    }

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        voice: str = "alloy",
        response_format: str = "mp3",
        timeout: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.voice = voice
        self.response_format = response_format
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if self._client is None:
            import openai

            self._client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    def synthesize(self, text: str) -> TTSResponse:
        start = time.perf_counter()
        try:
            response = self._get_client().audio.speech.create(
                model=self.model,
                input=text,
                voice=self.voice,
                response_format=self.response_format,
            )
            audio_bytes = bytes(response.content) if response.content else b""
        except Exception as exc:
            return TTSResponse(
                audio_bytes=b"",
                model=self.model,
                content_type="audio/wav",
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
                ok=False,
                error=str(exc),
            )
        result = TTSResponse(
            audio_bytes=audio_bytes,
            model=self.model,
            content_type=self._CONTENT_TYPES.get(self.response_format, "audio/mpeg"),
            elapsed_ms=(time.perf_counter() - start) * 1000.0,
        )
        logger.info(
            "TTS ok model=%s text_len=%s bytes=%s format=%s elapsed_ms=%.1f",
            result.model,
            len(text),
            len(result.audio_bytes),
            self.response_format,
            result.elapsed_ms,
        )
        return result