from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from app.core.config import settings
from app.integrations.openrouter_client import (
    LLMClient,
    OpenRouterLLMClient,
    build_provider_preferences,
)
from app.services.retrieval_service import RetrievedChunk

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Eres un asistente académico institucional. El contexto institucional proporcionado "
    "(reglamentos y normativas académicas) es la fuente de verdad: responde SOLO con base en él. "
    "No inventes información fuera del contexto y no respondas temas que no sean "
    "académico-institucionales. El historial de conversación solo sirve para entender referencias "
    "de seguimiento (pronombres, 'eso', 'lo anterior'); no lo uses como fuente de información. "
    "Cuando uses una fuente, cítala indicando el documento y el artículo o la página si está "
    "disponible. Sé conciso y formal."
)


@dataclass
class GenerationResult:
    text: str
    model: str
    tokens_input: int
    tokens_output: int
    elapsed_ms: float = 0.0
    ok: bool = True
    error: Optional[str] = None


class GenerationService:
    def __init__(
        self,
        client: Optional[LLMClient] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        provider: Optional[dict] = None,
        reasoning_effort: Optional[str] = None,
    ) -> None:
        resolved_model = model or settings.llm_model
        resolved_provider = (
            provider
            if provider is not None
            else build_provider_preferences(
                settings.llm_provider_order,
                settings.llm_provider_allow_fallbacks,
            )
        )
        resolved_reasoning = (
            reasoning_effort
            if reasoning_effort is not None
            else (settings.llm_reasoning_effort or None)
        )
        self.client = client or OpenRouterLLMClient(
            api_key=settings.openrouter_api_key or "",
            model=resolved_model,
            base_url=settings.openrouter_base_url,
            timeout=settings.llm_request_timeout,
            max_retries=settings.llm_max_retries,
            provider=resolved_provider,
            reasoning_effort=resolved_reasoning,
        )
        self.model = resolved_model
        self.temperature = (
            temperature if temperature is not None else settings.llm_temperature
        )
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.system_prompt = system_prompt or SYSTEM_PROMPT

    def generate(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        history: Optional[List[dict]] = None,
    ) -> GenerationResult:
        if not chunks:
            return GenerationResult(
                text="",
                model=self.model,
                tokens_input=0,
                tokens_output=0,
                ok=False,
                error="no context provided",
            )
        context = self._build_context(chunks)
        messages: List[dict] = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append(
            {
                "role": "user",
                "content": f"Contexto institucional:\n{context}\n\nPregunta: {query}",
            }
        )
        response = self.client.chat_completion(
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        if not response.ok:
            logger.error(
                "Generation failed model=%s error=%s elapsed_ms=%.1f",
                self.model,
                response.error,
                response.elapsed_ms,
            )
            return GenerationResult(
                text="",
                model=self.model,
                tokens_input=0,
                tokens_output=0,
                elapsed_ms=response.elapsed_ms,
                ok=False,
                error=response.error,
            )
        return GenerationResult(
            text=response.text,
            model=response.model,
            tokens_input=response.prompt_tokens,
            tokens_output=response.completion_tokens,
            elapsed_ms=response.elapsed_ms,
            ok=True,
        )

    def _build_context(self, chunks: List[RetrievedChunk]) -> str:
        blocks = [
            f"[Fuente {i + 1}: {chunk.document_title} | página {chunk.page_number}]\n{chunk.chunk_text}"
            for i, chunk in enumerate(chunks)
        ]
        return "\n\n".join(blocks)