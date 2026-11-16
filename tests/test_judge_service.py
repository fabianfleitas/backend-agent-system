from __future__ import annotations

from typing import List, Optional

from app.integrations.openrouter_client import LLMResponse
from app.services.judge_service import JudgeService
from app.services.retrieval_service import RetrievedChunk


class FakeJudgeClient:
    def __init__(self, text: str = "", ok: bool = True, error: Optional[str] = None) -> None:
        self.text = text
        self.ok = ok
        self.error = error
        self.messages: List[list] = []

    def chat_completion(self, messages: List[dict], temperature: float, max_tokens: int) -> LLMResponse:
        self.messages.append(messages)
        if not self.ok:
            return LLMResponse(text="", model="fake-judge", prompt_tokens=0, completion_tokens=0, ok=False, error=self.error)
        return LLMResponse(text=self.text, model="fake-judge", prompt_tokens=10, completion_tokens=5, ok=True)


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=1,
        document_id=7,
        document_version_id=6,
        document_title="Reglamento Académico.pdf",
        page_number=3,
        chunk_text="ARTICULO 10.- La matrícula requiere documentacion vigente.",
        similarity=0.85,
    )


def test_judge_parsea_json_valido() -> None:
    client = FakeJudgeClient(text='{"fidelidad": 0.95, "relevancia": 0.88, "contexto": 0.9, "observaciones": "ok"}')
    service = JudgeService(client=client)  # type: ignore[arg-type]
    result = service.evaluate(question="¿requisitos?", answer="Debe presentar documentación.", chunks=[_chunk()])
    assert result.ok
    assert result.fidelidad == 0.95
    assert result.relevancia == 0.88
    assert result.contexto == 0.9


def test_judge_parsea_json_embebido_y_con_claves() -> None:
    client = FakeJudgeClient(
        text='```json\n{"fidelidad": "0.8", "relevancia": 0.75, "contexto": 0.7}\n```'
    )
    service = JudgeService(client=client)  # type: ignore[arg-type]
    result = service.evaluate("pregunta", "respuesta", chunks=[_chunk()])
    assert result.ok
    assert result.fidelidad == 0.8
    assert result.relevancia == 0.75
    assert result.contexto == 0.7


def test_judge_error_de_cliente_devuelve_ok_false() -> None:
    client = FakeJudgeClient(ok=False, error="upstream timeout")
    service = JudgeService(client=client)  # type: ignore[arg-type]
    result = service.evaluate("pregunta", "respuesta", chunks=[_chunk()])
    assert not result.ok
    assert result.error == "upstream timeout"
    assert result.fidelidad == 0.0


def test_judge_sin_entrada_no_llama_al_cliente() -> None:
    client = FakeJudgeClient(text='{"fidelidad": 1, "relevancia": 1, "contexto": 1}')
    service = JudgeService(client=client)  # type: ignore[arg-type]
    result = service.evaluate(question="", answer="respuesta")
    assert not result.ok
    assert client.messages == []

def test_judge_service_explicit_model_reaches_client() -> None:
    service = JudgeService(model="institucion/juez-x")

    assert service.model == "institucion/juez-x"
    assert service.client.model == "institucion/juez-x"
