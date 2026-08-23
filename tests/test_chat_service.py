from __future__ import annotations

from typing import List, Optional

from app.core.config import settings
from app.core.security import AuthContext
from app.services.chat_service import ChatService, DOMAIN_GUARD_MESSAGE, LLM_UNAVAILABLE_MESSAGE
from app.services.retrieval_service import RetrievedChunk


class FakeUsersRepository:
    def get_or_create_user(self, auth: AuthContext) -> dict:
        return {"external_auth_id": auth.external_auth_id}


class FakeConversationsRepository:
    def __init__(self, conversation: Optional[dict]) -> None:
        self.conversation = conversation or {
            "id": 1,
            "external_auth_id": "student-1",
            "title": "Consultas",
        }
        self.touch_calls = 0

    def get_conversation(self, conversation_id: int) -> Optional[dict]:
        if conversation_id == self.conversation["id"]:
            return self.conversation
        return None

    def touch_conversation(self, conversation_id: int) -> None:
        self.touch_calls += 1


class FakeMessagesRepository:
    def __init__(self) -> None:
        self.messages: List[dict] = []
        self.next_id = 1

    def create_message(self, **kwargs) -> dict:
        record = {"id": self.next_id}
        record.update(kwargs)
        self.next_id += 1
        self.messages.append(record)
        return record

    def update_message_audit_id(self, message_id: int, audit_id: str) -> dict:
        for m in self.messages:
            if m["id"] == message_id:
                m["audit_id"] = audit_id
                return m
        return self.messages[-1]

    def get_conversation_messages(self, conversation_id: int) -> list[dict]:
        return [m for m in self.messages if m.get("conversation_id") == conversation_id]


class FakeAuditRepository:
    def __init__(self) -> None:
        self.logs: List[dict] = []
        self.next_id = 0

    def create_audit_log(self, **kwargs) -> dict:
        self.next_id += 1
        record = {"id": f"audit-{self.next_id}"}
        record.update(kwargs)
        self.logs.append(record)
        return record


class FakeMessageDocumentsRepository:
    def __init__(self) -> None:
        self.rows: List[dict] = []
        self.fail_with: Optional[Exception] = None

    def insert_message_documents(self, rows: List[dict]) -> List[dict]:
        if self.fail_with is not None:
            raise self.fail_with
        self.rows.extend(rows)
        return list(rows)


class FakeFeedbackRepository:
    pass


class FakeRetrievalService:
    def __init__(self, result=None) -> None:
        self.result = result
        self.calls: List[str] = []
        self.retrieved = False

    def retrieve(self, query: str):
        self.calls.append(query)
        self.retrieved = True
        return self.result


class _RetrievalResult:
    def __init__(self, chunks: List[RetrievedChunk], ok: bool = True, error: Optional[str] = None) -> None:
        self.chunks = chunks
        self.total = len(chunks)
        self.ok = ok
        self.error = error


class _GenerationResult:
    def __init__(
        self,
        ok: bool = True,
        text: str = "Respuesta real del LLM sobre el reglamento.",
        model: str = "fake-llm-gpt",
        tokens_input: int = 120,
        tokens_output: int = 40,
        error: Optional[str] = None,
    ) -> None:
        self.text = text
        self.model = model
        self.tokens_input = tokens_input
        self.tokens_output = tokens_output
        self.ok = ok
        self.error = error


class FakeGenerationService:
    def __init__(self, result=None) -> None:
        self.result = result
        self.calls: List[tuple] = []

    def generate(self, query: str, chunks: List[RetrievedChunk], history=None):
        self.calls.append((query, chunks, history))
        return self.result or _GenerationResult()


def _chunk(chunk_id: int, similarity: float = 0.85) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=7,
        document_version_id=6,
        document_title="Reglamento Académico.pdf",
        page_number=3,
        chunk_text="ARTICULO 10.- La matrícula requiere documentacion vigente.",
        similarity=similarity,
    )


def _auth() -> AuthContext:
    return AuthContext(external_auth_id="student-1", auth_provider="delegated", tipo_usuario="ESTUDIANTE")


def _make_service(
    retrieval_result=None,
    conversation: Optional[dict] = None,
    message_docs_repo: Optional[FakeMessageDocumentsRepository] = None,
    generation_result=None,
) -> tuple[ChatService, FakeRetrievalService, FakeMessageDocumentsRepository, FakeMessagesRepository, FakeAuditRepository, FakeGenerationService]:
    conv = FakeConversationsRepository(conversation)
    messages = FakeMessagesRepository()
    audit = FakeAuditRepository()
    md = message_docs_repo or FakeMessageDocumentsRepository()
    retrieval = FakeRetrievalService(retrieval_result)
    generation = FakeGenerationService(generation_result)
    service = ChatService(
        conversations_repository=conv,
        messages_repository=messages,
        audit_repository=audit,
        feedback_repository=FakeFeedbackRepository(),
        users_repository=FakeUsersRepository(),
        retrieval_service=retrieval,
        message_documents_repository=md,
        generation_service=generation,
    )
    return service, retrieval, md, messages, audit, generation


def test_chat_with_context_returns_sources_and_persists_traceability(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", False)
    retrieval_result = _RetrievalResult([_chunk(10, 0.85), _chunk(11, 0.72)])
    service, retrieval, md, messages, audit, generation = _make_service(retrieval_result)
    result = service.answer_text_query(_auth(), 1, "¿requisitos para matrícula?")
    assert result is not None
    assert result.sources
    assert result.sources[0]["document_id"] == 7
    assert result.sources[0]["document"] == "Reglamento Académico.pdf"
    assert result.sources[1]["similarity_score"] == 0.72
    assert "Recuperé 2 fragmentos" in result.response
    assert retrieval.retrieved
    assert generation.calls == []
    assert len(md.rows) == 2
    row = md.rows[0]
    assert row["chunk_id"] == 10
    assert row["similarity_score"] == 0.85
    assert row["documento_id"] == 7
    assert row["documento_version_id"] == 6
    assert row["audit_id"] == result.audit_log["id"]
    assert result.assistant_message["modelo_ia"] == "mock-retrieval"
    assert audit.logs[0]["embedding_model"] == settings.embedding_model
    assert "GUARD" not in audit.logs[0]["observaciones"]


def test_chat_without_context_returns_guard_and_no_traceability(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    service, retrieval, md, messages, audit, generation = _make_service(_RetrievalResult([]))
    result = service.answer_text_query(_auth(), 1, "¿cuál es la capital de Francia?")
    assert result is not None
    assert result.response == DOMAIN_GUARD_MESSAGE
    assert result.sources == []
    assert md.rows == []
    assert result.assistant_message["modelo_ia"] == "mock"
    assert audit.logs[0]["embedding_model"] is None
    assert "GUARD" in audit.logs[0]["observaciones"]
    assert retrieval.retrieved
    assert generation.calls == []


def test_chat_retrieval_failure_falls_back_to_mock(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    failed = _RetrievalResult([], ok=False, error="openai down")
    service, retrieval, md, messages, audit, _ = _make_service(failed)
    result = service.answer_text_query(_auth(), 1, "consulta institucional")
    assert result is not None
    assert result.response.startswith("MOCK: Recibí")
    assert result.sources == []
    assert md.rows == []
    assert result.assistant_message["modelo_ia"] == "mock"


def test_chat_with_embeddings_disabled_skips_retrieval(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", False)
    service, retrieval, md, messages, _, generation = _make_service()
    result = service.answer_text_query(_auth(), 1, "¿horarios?")
    assert result is not None
    assert result.response.startswith("MOCK: Recibí")
    assert result.sources == []
    assert md.rows == []
    assert not retrieval.retrieved
    assert retrieval.calls == []
    assert generation.calls == []


def test_chat_conversation_not_found_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    service, _, _, _, _, _ = _make_service(_RetrievalResult([]), conversation={"id": 99, "external_auth_id": "otro"})
    result = service.answer_text_query(_auth(), 1, "consulta")
    assert result is None


def test_chat_traceability_failure_does_not_break(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", False)
    md = FakeMessageDocumentsRepository()
    md.fail_with = RuntimeError("db down")
    service, _, _, _, _, generation = _make_service(_RetrievalResult([_chunk(10)]), message_docs_repo=md)
    result = service.answer_text_query(_auth(), 1, "requisitos matrícula")
    assert result is not None
    assert result.sources
    assert len(result.sources) == 1
    assert generation.calls == []


def test_chat_llm_success_uses_real_response(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    retrieval_result = _RetrievalResult([_chunk(10, 0.85)])
    generation_result = _GenerationResult(text="Según el artículo del reglamento, la matrícula requiere documentación vigente.")
    service, retrieval, md, messages, audit, generation = _make_service(retrieval_result, generation_result=generation_result)
    result = service.answer_text_query(_auth(), 1, "¿requisitos para matrícula?")
    assert result is not None
    assert result.response == generation_result.text
    assert result.sources
    assert len(result.sources) == 1
    assert len(generation.calls) == 1
    query, chunks, _history = generation.calls[0]
    assert query == "¿requisitos para matrícula?"
    assert len(chunks) == 1
    assert result.assistant_message["modelo_ia"] == "fake-llm-gpt"
    assert result.assistant_message["tokens_input"] == 120
    assert result.assistant_message["tokens_output"] == 40
    assert audit.logs[0]["modelo_ia"] == "fake-llm-gpt"
    assert audit.logs[0]["observaciones"] == "LLM: OpenRouter (contexto RAG) [text]"
    assert len(md.rows) == 1


def test_chat_llm_failure_returns_controlled_fallback_with_real_sources(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    retrieval_result = _RetrievalResult([_chunk(10, 0.85), _chunk(11, 0.72)])
    generation_result = _GenerationResult(ok=False, error="openrouter timeout")
    service, retrieval, md, messages, audit, generation = _make_service(retrieval_result, generation_result=generation_result)
    result = service.answer_text_query(_auth(), 1, "¿requisitos para matrícula?")
    assert result is not None
    assert result.response == LLM_UNAVAILABLE_MESSAGE
    assert len(result.sources) == 2
    assert len(generation.calls) == 1
    assert result.assistant_message["modelo_ia"] == settings.llm_model
    assert result.assistant_message["tokens_input"] is None
    assert result.assistant_message["tokens_output"] is None
    assert audit.logs[0]["observaciones"].startswith("LLM_FAILED:")
    assert "openrouter timeout" in audit.logs[0]["observaciones"]
    assert len(md.rows) == 2


def test_chat_llm_without_context_never_calls_llm(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    service, retrieval, md, messages, audit, generation = _make_service(_RetrievalResult([]))
    result = service.answer_text_query(_auth(), 1, "¿cuál es la capital de Francia?")
    assert result is not None
    assert result.response == DOMAIN_GUARD_MESSAGE
    assert result.sources == []
    assert generation.calls == []
    assert retrieval.retrieved


def test_voice_llm_success_uses_real_answer(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", True)
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    retrieval_result = _RetrievalResult([_chunk(10, 0.85)])
    generation_result = _GenerationResult(text="Según el reglamento, para matricularse necesita documentación vigente.")
    service, retrieval, md, messages, audit, generation = _make_service(
        retrieval_result, generation_result=generation_result
    )
    result = service.answer_voice_query(_auth(), 1, "¿requisitos para matrícula?")
    assert result is not None
    assert result.response == generation_result.text
    assert result.sources
    assert len(result.sources) == 1
    assert len(generation.calls) == 1
    query, chunks, _history = generation.calls[0]
    assert query == "¿requisitos para matrícula?"
    assert len(chunks) == 1
    assert result.assistant_message["modelo_ia"] == "fake-llm-gpt"
    assert audit.logs[0]["modelo_ia"] == "fake-llm-gpt"
    assert audit.logs[0]["observaciones"] == "LLM: OpenRouter (contexto RAG) [voice]"
    assert len(md.rows) == 1


def test_voice_no_context_returns_guard(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", True)
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    service, retrieval, md, messages, audit, generation = _make_service(_RetrievalResult([]))
    result = service.answer_voice_query(_auth(), 1, "¿cuál es la capital de Francia?")
    assert result is not None
    assert result.response == DOMAIN_GUARD_MESSAGE
    assert result.sources == []
    assert md.rows == []
    assert generation.calls == []
    assert audit.logs[0]["observaciones"] == "GUARD: sin contexto institucional recuperado [voice]"


def test_voice_llm_failure_returns_fallback_with_real_sources(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", True)
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    retrieval_result = _RetrievalResult([_chunk(10, 0.85), _chunk(11, 0.72)])
    generation_result = _GenerationResult(ok=False, error="openrouter timeout")
    service, retrieval, md, messages, audit, generation = _make_service(retrieval_result, generation_result=generation_result)
    result = service.answer_voice_query(_auth(), 1, "¿requisitos?")
    assert result is not None
    assert result.response == LLM_UNAVAILABLE_MESSAGE
    assert len(result.sources) == 2
    assert len(md.rows) == 2
    assert audit.logs[0]["observaciones"].startswith("LLM_FAILED:")
    assert "[voice]" in audit.logs[0]["observaciones"]


def test_voice_stt_disabled_uses_mock_without_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", False)
    service, retrieval, md, messages, audit, generation = _make_service()
    result = service.answer_voice_query(_auth(), 1, "transcripción mock")
    assert result is not None
    assert result.response == "MOCK: respuesta simulada basada en reglamentos institucionales (voz sin STT real)"
    assert result.sources == []
    assert md.rows == []
    assert generation.calls == []
    assert not retrieval.retrieved
    assert audit.logs[0]["observaciones"] == "MOCK: sin evaluación automática [voice]"


def test_voice_conversation_not_found_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stt_enabled", True)
    service, _, _, _, _, _ = _make_service(_RetrievalResult([]), conversation={"id": 99, "external_auth_id": "otro"})
    result = service.answer_voice_query(_auth(), 1, "¿requisitos?")
    assert result is None


def test_history_included_in_llm_call(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_history_enabled", True)
    retrieval_result = _RetrievalResult([_chunk(10, 0.85)])
    service, retrieval, md, messages, audit, generation = _make_service(retrieval_result)
    messages.create_message(conversation_id=1, rol_mensaje="USER", contenido_texto="turno1 pregunta")
    messages.create_message(conversation_id=1, rol_mensaje="ASSISTANT", contenido_texto="turno1 respuesta")
    result = service.answer_text_query(_auth(), 1, "¿y eso qué significa?")
    assert result is not None
    query, chunks, history = generation.calls[0]
    assert query == "¿y eso qué significa?"
    assert len(chunks) == 1
    assert history == [
        {"role": "user", "content": "turno1 pregunta"},
        {"role": "assistant", "content": "turno1 respuesta"},
    ]


def test_history_excludes_llm_unavailable_and_current(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_history_enabled", True)
    retrieval_result = _RetrievalResult([_chunk(10, 0.85)])
    service, retrieval, md, messages, audit, generation = _make_service(retrieval_result)
    messages.create_message(conversation_id=1, rol_mensaje="ASSISTANT", contenido_texto=LLM_UNAVAILABLE_MESSAGE)
    messages.create_message(conversation_id=1, rol_mensaje="USER", contenido_texto="turno real")
    messages.create_message(conversation_id=1, rol_mensaje="ASSISTANT", contenido_texto="respuesta real")
    result = service.answer_text_query(_auth(), 1, "consulta actual")
    assert result is not None
    query, chunks, history = generation.calls[0]
    assert history == [
        {"role": "user", "content": "turno real"},
        {"role": "assistant", "content": "respuesta real"},
    ]


def test_history_excludes_other_conversation(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_history_enabled", True)
    retrieval_result = _RetrievalResult([_chunk(10, 0.85)])
    service, retrieval, md, messages, audit, generation = _make_service(retrieval_result)
    messages.create_message(conversation_id=99, rol_mensaje="USER", contenido_texto="otra conversacion")
    result = service.answer_text_query(_auth(), 1, "consulta")
    assert result is not None
    query, chunks, history = generation.calls[0]
    assert history == []


def test_history_disabled_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_history_enabled", False)
    retrieval_result = _RetrievalResult([_chunk(10, 0.85)])
    service, retrieval, md, messages, audit, generation = _make_service(retrieval_result)
    messages.create_message(conversation_id=1, rol_mensaje="USER", contenido_texto="turno")
    result = service.answer_text_query(_auth(), 1, "consulta")
    assert result is not None
    query, chunks, history = generation.calls[0]
    assert history == []


def test_history_budget_truncates_oldest(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_history_enabled", True)
    monkeypatch.setattr(settings, "llm_history_max_tokens", 30)
    monkeypatch.setattr(settings, "llm_history_max_messages", 10)
    retrieval_result = _RetrievalResult([_chunk(10, 0.85)])
    service, retrieval, md, messages, audit, generation = _make_service(retrieval_result)
    messages.create_message(conversation_id=1, rol_mensaje="USER", contenido_texto="mensaje largooooooo " * 20)
    messages.create_message(conversation_id=1, rol_mensaje="ASSISTANT", contenido_texto="uno corto")
    result = service.answer_text_query(_auth(), 1, "consulta")
    assert result is not None
    query, chunks, history = generation.calls[0]
    assert all(m["content"] == "uno corto" for m in history)
    assert len(history) == 1