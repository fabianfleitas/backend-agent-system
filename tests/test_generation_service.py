from __future__ import annotations

from typing import List, Optional

from app.integrations.openrouter_client import LLMResponse
from app.services.generation_service import GenerationService, SYSTEM_PROMPT
from app.services.retrieval_service import RetrievedChunk


class FakeLLMClient:
    def __init__(
        self,
        text: str = "Respuesta institucional generada.",
        model: str = "fake-llm",
        fail_with: Optional[Exception] = None,
    ) -> None:
        self.text = text
        self.model = model
        self.fail_with = fail_with
        self.calls: List[dict] = []

    def chat_completion(self, messages: List[dict], temperature: float, max_tokens: int) -> LLMResponse:
        self.calls.append(
            {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        )
        if self.fail_with is not None:
            return LLMResponse(text="", model=self.model, prompt_tokens=0, completion_tokens=0, ok=False, error=str(self.fail_with))
        content = "".join(m.get("content", "") for m in messages)
        return LLMResponse(
            text=self.text,
            model=self.model,
            prompt_tokens=len(content.split()),
            completion_tokens=10,
        )


def _chunk(index: int, title: str = "Reglamento.pdf") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=index,
        document_id=7,
        document_version_id=6,
        document_title=title,
        page_number=2,
        chunk_text=f"ARTICULO {index}.- Norma institucional de prueba.",
        similarity=0.8,
    )


def _make_service(client: Optional[FakeLLMClient] = None) -> tuple[GenerationService, FakeLLMClient]:
    fake = client or FakeLLMClient()
    service = GenerationService(
        client=fake,
        model="fake-llm",
        temperature=0.1,
        max_tokens=256,
        system_prompt="prompt de prueba",
    )
    return service, fake


def test_generate_returns_text_and_tokens() -> None:
    service, _ = _make_service()
    result = service.generate("¿requisitos de matrícula?", [_chunk(1), _chunk(2)])
    assert result.ok
    assert result.error is None
    assert result.text == "Respuesta institucional generada."
    assert result.model == "fake-llm"
    assert result.tokens_input > 0
    assert result.tokens_output == 10
    assert result.elapsed_ms >= 0


def test_generate_builds_context_with_sources() -> None:
    service, fake = _make_service()
    service.generate("¿requisitos?", [_chunk(1), _chunk(2, title="Reglamento de Evaluación.pdf")])
    messages = fake.calls[-1]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "prompt de prueba"
    user = messages[1]["content"]
    assert "¿requisitos?" in user
    assert "[Fuente 1: Reglamento.pdf | página 2]" in user
    assert "[Fuente 2: Reglamento de Evaluación.pdf | página 2]" in user
    assert "ARTICULO 1" in user
    assert "ARTICULO 2" in user


def test_generate_passes_temperature_and_max_tokens() -> None:
    service, fake = _make_service()
    service.generate("pregunta", [_chunk(1)])
    call = fake.calls[-1]
    assert call["temperature"] == 0.1
    assert call["max_tokens"] == 256


def test_generate_uses_default_system_prompt() -> None:
    fake = FakeLLMClient()
    service = GenerationService(client=fake, model="fake-llm")
    service.generate("pregunta", [_chunk(1)])
    assert fake.calls[-1]["messages"][0]["content"] == SYSTEM_PROMPT


def test_generate_client_failure_returns_not_ok() -> None:
    service, _ = _make_service(FakeLLMClient(fail_with=RuntimeError("openrouter down")))
    result = service.generate("pregunta", [_chunk(1)])
    assert not result.ok
    assert result.error == "openrouter down"
    assert result.text == ""
    assert result.tokens_input == 0
    assert result.tokens_output == 0


def test_generate_without_context_returns_not_ok_and_skips_client() -> None:
    client = FakeLLMClient()
    service = GenerationService(client=client, model="fake-llm")
    result = service.generate("pregunta", [])
    assert not result.ok
    assert result.error == "no context provided"
    assert client.calls == []


def test_generate_inserts_history_between_system_and_user() -> None:
    service, fake = _make_service()
    history = [
        {"role": "user", "content": "turno 1 pregunta"},
        {"role": "assistant", "content": "turno 1 respuesta"},
    ]
    service.generate("turno 2 pregunta", [_chunk(1)], history=history)
    messages = fake.calls[-1]["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[1]["content"] == "turno 1 pregunta"
    assert messages[2]["content"] == "turno 1 respuesta"
    assert "turno 2 pregunta" in messages[3]["content"]


def test_generate_without_history_has_only_system_and_user() -> None:
    service, fake = _make_service()
    service.generate("pregunta", [_chunk(1)])
    messages = fake.calls[-1]["messages"]
    assert [m["role"] for m in messages] == ["system", "user"]


def test_generate_with_empty_history_ignores_it() -> None:
    service, fake = _make_service()
    service.generate("pregunta", [_chunk(1)], history=[])
    messages = fake.calls[-1]["messages"]
    assert [m["role"] for m in messages] == ["system", "user"]