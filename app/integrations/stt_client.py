from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class STTResponse:
    text: str
    model: str
    duration: Optional[float]
    elapsed_ms: float = 0.0
    ok: bool = True
    error: Optional[str] = None


class STTClient(Protocol):
    def transcribe(self, audio_bytes: bytes, filename: str, content_type: Optional[str]) -> STTResponse: ...


class OpenAICompatibleSTTClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        response_format: str = "verbose_json",
        timeout: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
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

    def transcribe(self, audio_bytes: bytes, filename: str, content_type: Optional[str]) -> STTResponse:
        start = time.perf_counter()
        try:
            response = self._get_client().audio.transcriptions.create(
                model=self.model,
                file=(filename, audio_bytes, content_type),
                response_format=self.response_format,
            )
            duration = getattr(response, "duration", None)
            result = STTResponse(
                text=(getattr(response, "text", None) or "").strip(),
                model=getattr(response, "model", None) or self.model,
                duration=float(duration) if duration is not None else None,
            )
        except Exception as exc:
            return STTResponse(
                text="",
                model=self.model,
                duration=None,
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
                ok=False,
                error=str(exc),
            )
        result.elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "STT ok model=%s text_len=%s duration=%s elapsed_ms=%.1f",
            result.model,
            len(result.text),
            result.duration,
            result.elapsed_ms,
        )
        return result