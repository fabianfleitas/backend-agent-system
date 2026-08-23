from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    elapsed_ms: float = 0.0
    ok: bool = True
    error: Optional[str] = None


class LLMClient(Protocol):
    def chat_completion(
        self,
        messages: List[dict],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse: ...


class OpenRouterLLMClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 45.0,
        max_retries: int = 1,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
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

    def chat_completion(
        self,
        messages: List[dict],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        start = time.perf_counter()
        try:
            response = self._get_client().chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            result = LLMResponse(
                text=response.choices[0].message.content or "",
                model=response.model or self.model,
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
            )
        except Exception as exc:
            return LLMResponse(
                text="",
                model=self.model,
                prompt_tokens=0,
                completion_tokens=0,
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
                ok=False,
                error=str(exc),
            )
        result.elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "LLM ok model=%s prompt_tokens=%s completion_tokens=%s elapsed_ms=%.1f",
            result.model,
            result.prompt_tokens,
            result.completion_tokens,
            result.elapsed_ms,
        )
        return result