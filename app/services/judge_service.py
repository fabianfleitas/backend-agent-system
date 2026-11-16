from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from app.core.config import settings
from app.integrations.openrouter_client import LLMClient, OpenRouterLLMClient
from app.services.retrieval_service import RetrievedChunk

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = (
    "Eres un evaluador imparcial de respuestas generadas por un asistente académico "
    "institucional (metodología LLM-as-a-Judge). Evalúa la respuesta del asistente frente "
    "al contexto institucional recuperado (fuente de verdad). Responde ÚNICAMENTE con un "
    "objeto JSON sin texto adicional, con esta forma exacta:\n"
    '{"fidelidad": <0-1>, "relevancia": <0-1>, "contexto": <0-1>, "observaciones": "<breve>"}\n'
    "Criterios: fidelidad = la respuesta no alucina y se apoya en el contexto; "
    "relevancia = la respuesta atiende la intención de la pregunta; "
    "contexto = la respuesta usa correctamente la información recuperada."
)

# Umbrf_de reemplazo para tokens sin coincidencia (evita restos de JSON).
_FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+")


@dataclass
class JudgeResult:
    fidelidad: float
    relevancia: float
    contexto: float
    model: str
    raw: str = ""
    ok: bool = True
    error: Optional[str] = None


class JudgeService:
    """Evalúa una respuesta con LLM-as-a-Judge y devuelve puntajes 0–1."""

    def __init__(
        self,
        client: Optional[LLMClient] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        resolved_model = model or settings.judge_model
        self.client = client or OpenRouterLLMClient(
            api_key=settings.openrouter_api_key or "",
            model=resolved_model,
            base_url=settings.openrouter_base_url,
            timeout=settings.judge_request_timeout,
            max_retries=settings.llm_max_retries,
        )
        self.model = resolved_model
        self.temperature = (
            temperature if temperature is not None else settings.judge_temperature
        )
        self.max_tokens = max_tokens or settings.judge_max_tokens

    def evaluate(
        self,
        question: str,
        answer: str,
        chunks: Optional[List[RetrievedChunk]] = None,
    ) -> JudgeResult:
        if not question or not answer:
            return JudgeResult(
                fidelidad=0.0,
                relevancia=0.0,
                contexto=0.0,
                model=self.model,
                ok=False,
                error="empty question or answer",
            )
        context = self._build_context(chunks or [])
        prompt = (
            f"Contexto institucional recuperado:\n{context or '(sin contexto)'}\n\n"
            f"Pregunta del estudiante: {question}\n\n"
            f"Respuesta del asistente a evaluar:\n{answer}"
        )
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = self.client.chat_completion(
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        if not response.ok:
            logger.error("Judge failed model=%s error=%s", self.model, response.error)
            return JudgeResult(
                fidelidad=0.0,
                relevancia=0.0,
                contexto=0.0,
                model=response.model or self.model,
                ok=False,
                error=response.error,
            )
        return self._parse(response.text, response.model or self.model)

    def _parse(self, raw: str, model: str) -> JudgeResult:
        data = self._extract_json(raw)
        if data is None:
            return JudgeResult(
                fidelidad=0.0,
                relevancia=0.0,
                contexto=0.0,
                model=model,
                raw=raw,
                ok=False,
                error="judge response not JSON",
            )
        try:
            fidelidad = _clamp(float(data.get("fidelidad", 0)))
            relevancia = _clamp(float(data.get("relevancia", 0)))
            contexto = _clamp(float(data.get("contexto", 0)))
        except (TypeError, ValueError):
            return JudgeResult(
                fidelidad=0.0,
                relevancia=0.0,
                contexto=0.0,
                model=model,
                raw=raw,
                ok=False,
                error="invalid score values",
            )
        return JudgeResult(
            fidelidad=fidelidad,
            relevancia=relevancia,
            contexto=contexto,
            model=model,
            raw=raw,
            ok=True,
        )

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        if not text:
            return None
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.MULTILINE)
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
        # Fallback: extraer el primer objeto JSON embebido en el texto.
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _build_context(chunks: List[RetrievedChunk]) -> str:
        blocks = [
            f"[Fuente {i + 1}: {chunk.document_title} | página {chunk.page_number}]\n{chunk.chunk_text}"
            for i, chunk in enumerate(chunks)
        ]
        return "\n\n".join(blocks)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))