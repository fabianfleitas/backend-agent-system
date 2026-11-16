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
            "institucion_id": 1,
        }
        self.touch_calls = 0

    def get_conversation(self, conversation_id: int, institucion_id: Optional[int] = None) -> Optional[dict]:
        if conversation_id == self.conversation["id"]:
            # Si se filtra por institución, debe coincidir (para aislamiento)
            if institucion_id is not None and self.conversation.get("institucion_id") != institucion_id:
                return None
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

    def update_message(self, message_id: int, **fields) -> dict:
        for m in self.messages:
            if m["id"] == message_id:
                m.update(fields)
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

    def update_observaciones(self, audit_id: str, observaciones: str) -> Optional[dict]:
        for log in self.logs:
            if log["id"] == audit_id:
                log["observaciones"] = observaciones
                return log
        return None


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

    def retrieve(self, query: str, institucion_id: Optional[int] = None):
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
    return AuthContext(external_auth_id="student-1", institucion_id=1, tipo_miembro="ESTUDIANTE", is_platform_admin=False)


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
    assert result.assistant_message["modelo_ia"] == "fake-llm-gpt"
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


class FakeHandoffService:
    def __init__(self, motivo: Optional[str] = None) -> None:
        self.motivo = motivo
        self.should_calls: List[dict] = []
        self.created: List[dict] = []

    def should_escalate(self, message, institucion_id=None, guard_triggered=False, llm_failed=False):
        self.should_calls.append(
            {
                "message": message,
                "institucion_id": institucion_id,
                "guard_triggered": guard_triggered,
                "llm_failed": llm_failed,
            }
        )
        return self.motivo

    def create_escalation(self, **kwargs) -> dict:
        self.created.append(kwargs)
        return {"id": 1, "datos": {"motivo": kwargs.get("motivo")}}


def test_chat_guard_creates_escalation_when_handoff(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    retrieval_result = _RetrievalResult([])  # sin contexto → guard
    conv = FakeConversationsRepository({"id": 1, "external_auth_id": "student-1", "institucion_id": 1})
    messages = FakeMessagesRepository()
    audit = FakeAuditRepository()
    md = FakeMessageDocumentsRepository()
    retrieval = FakeRetrievalService(retrieval_result)
    generation = FakeGenerationService()
    handoff = FakeHandoffService(motivo="DOMAIN_OUT_OF_SCOPE")
    service = ChatService(
        conversations_repository=conv,
        messages_repository=messages,
        audit_repository=audit,
        feedback_repository=FakeFeedbackRepository(),
        users_repository=FakeUsersRepository(),
        retrieval_service=retrieval,
        message_documents_repository=md,
        generation_service=generation,
        handoff_service=handoff,  # type: ignore[arg-type]
    )
    result = service.answer_text_query(_auth(), 1, "¿cuál es la capital de Francia?")
    assert result is not None
    assert result.response == DOMAIN_GUARD_MESSAGE
    assert len(handoff.created) == 1
    assert handoff.created[0]["motivo"] == "DOMAIN_OUT_OF_SCOPE"
    assert handoff.created[0]["audit_id"] == result.audit_log["id"]
    assert "HANDOFF:DOMAIN_OUT_OF_SCOPE" in result.audit_log["observaciones"]


def test_chat_guard_sin_handoff_no_escala(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    retrieval_result = _RetrievalResult([])
    conv = FakeConversationsRepository({"id": 1, "external_auth_id": "student-1", "institucion_id": 1})
    messages = FakeMessagesRepository()
    audit = FakeAuditRepository()
    md = FakeMessageDocumentsRepository()
    retrieval = FakeRetrievalService(retrieval_result)
    generation = FakeGenerationService()
    handoff = FakeHandoffService(motivo=None)
    service = ChatService(
        conversations_repository=conv,
        messages_repository=messages,
        audit_repository=audit,
        feedback_repository=FakeFeedbackRepository(),
        users_repository=FakeUsersRepository(),
        retrieval_service=retrieval,
        message_documents_repository=md,
        generation_service=generation,
        handoff_service=handoff,  # type: ignore[arg-type]
    )
    result = service.answer_text_query(_auth(), 1, "¿cuál es la capital de Francia?")
    assert result is not None
    assert result.response == DOMAIN_GUARD_MESSAGE
    assert handoff.created == []
    assert "HANDOFF" not in result.audit_log["observaciones"]


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


def test_regenerate_reemplaza_ultima_respuesta_in_place(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    conv = FakeConversationsRepository({"id": 1, "external_auth_id": "student-1", "institucion_id": 1})
    messages = FakeMessagesRepository()
    messages.create_message(conversation_id=1, rol_mensaje="USER", contenido_texto="¿requisitos para matrícula?")
    messages.create_message(conversation_id=1, rol_mensaje="ASSISTANT", contenido_texto="respuesta anterior")
    audit = FakeAuditRepository()
    md = FakeMessageDocumentsRepository()
    retrieval = FakeRetrievalService(_RetrievalResult([_chunk(10, 0.85)]))
    generation = FakeGenerationService(_GenerationResult(text="Respuesta regenerada."))
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
    result = service.regenerate(_auth(), 1)
    assert result is not None
    assert result["response"] == "Respuesta regenerada."
    assert result["assistant_message"]["contenido_texto"] == "Respuesta regenerada."
    # In-place: no se agrega turno nuevo
    assert len(messages.messages) == 2
    assert len(audit.logs) == 1
    assert "[regenerate]" in audit.logs[0]["observaciones"]
    assert len(md.rows) == 1
    assert md.rows[0]["audit_id"] == result["audit_id"]


def test_regenerate_sin_turno_previo_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    conv = FakeConversationsRepository({"id": 1, "external_auth_id": "student-1", "institucion_id": 1})
    messages = FakeMessagesRepository()
    messages.create_message(conversation_id=1, rol_mensaje="USER", contenido_texto="hola")
    service = ChatService(
        conversations_repository=conv,
        messages_repository=messages,
        audit_repository=FakeAuditRepository(),
        feedback_repository=FakeFeedbackRepository(),
        users_repository=FakeUsersRepository(),
    )
    assert service.regenerate(_auth(), 1) is None  # no hay mensaje ASSISTANT


class FakeJudgeService:
    def __init__(
        self,
        ok: bool = True,
        fidelidad: float = 0.9,
        relevancia: float = 0.8,
        contexto: float = 0.85,
        error: Optional[str] = None,
    ) -> None:
        self.ok = ok
        self.fidelidad = fidelidad
        self.relevancia = relevancia
        self.contexto = contexto
        self.error = error
        self.calls: List[tuple] = []

    def evaluate(self, question: str, answer: str, chunks=None):
        self.calls.append((question, answer, chunks))
        if not self.ok:
            from app.services.judge_service import JudgeResult

            return JudgeResult(
                fidelidad=0.0,
                relevancia=0.0,
                contexto=0.0,
                model="fake-judge",
                ok=False,
                error=self.error,
            )
        from app.services.judge_service import JudgeResult

        return JudgeResult(
            fidelidad=self.fidelidad,
            relevancia=self.relevancia,
            contexto=self.contexto,
            model="fake-judge",
            ok=True,
        )


def test_chat_judge_enabled_persists_scores(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "judge_enabled", True)
    # Corrida de evaluación: el muestreo se fuerza a 100 %.
    monkeypatch.setattr(settings, "judge_sample_rate", 1.0)
    # Independiente de la DB real: la config de chat se resuelve por el default.
    from app.services.config_service import ConfigService

    monkeypatch.setattr(
        ConfigService, "get_bool", lambda self, clave, institucion_id=None, default=False: default
    )
    monkeypatch.setattr(
        ConfigService, "get_float", lambda self, clave, institucion_id=None, default=0.0: default
    )
    retrieval_result = _RetrievalResult([_chunk(10, 0.85)])
    generation_result = _GenerationResult(text="La matrícula requiere documentación vigente.")
    conv = FakeConversationsRepository({"id": 1, "external_auth_id": "student-1", "institucion_id": 1})
    messages = FakeMessagesRepository()
    audit = FakeAuditRepository()
    md = FakeMessageDocumentsRepository()
    retrieval = FakeRetrievalService(retrieval_result)
    generation = FakeGenerationService(generation_result)
    judge = FakeJudgeService()
    service = ChatService(
        conversations_repository=conv,
        messages_repository=messages,
        audit_repository=audit,
        feedback_repository=FakeFeedbackRepository(),
        users_repository=FakeUsersRepository(),
        retrieval_service=retrieval,
        message_documents_repository=md,
        generation_service=generation,
        judge_service=judge,  # type: ignore[arg-type]
    )
    result = service.answer_text_query(_auth(), 1, "¿requisitos para matrícula?")
    assert result is not None
    assert len(judge.calls) == 1
    assert result.audit_log["score_fidelidad"] == 0.9
    assert result.audit_log["score_relevancia"] == 0.8
    assert result.audit_log["score_contexto"] == 0.85
    assert "JUDGE:ok" in result.audit_log["observaciones"]
    assert result.timings_ms["judge"] >= 0
    assert result.timings_ms["service_total"] >= result.timings_ms["judge"]


def test_chat_judge_sampling_rate_zero_skips_judge(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "judge_enabled", True)
    monkeypatch.setattr(settings, "judge_sample_rate", 0.0)
    from app.services.config_service import ConfigService

    monkeypatch.setattr(
        ConfigService, "get_bool", lambda self, clave, institucion_id=None, default=False: default
    )
    monkeypatch.setattr(
        ConfigService, "get_float", lambda self, clave, institucion_id=None, default=0.0: default
    )
    retrieval_result = _RetrievalResult([_chunk(10, 0.85)])
    generation_result = _GenerationResult(text="Respuesta.")
    conv = FakeConversationsRepository({"id": 1, "external_auth_id": "student-1", "institucion_id": 1})
    messages = FakeMessagesRepository()
    audit = FakeAuditRepository()
    md = FakeMessageDocumentsRepository()
    retrieval = FakeRetrievalService(retrieval_result)
    generation = FakeGenerationService(generation_result)
    judge = FakeJudgeService()
    service = ChatService(
        conversations_repository=conv,
        messages_repository=messages,
        audit_repository=audit,
        feedback_repository=FakeFeedbackRepository(),
        users_repository=FakeUsersRepository(),
        retrieval_service=retrieval,
        message_documents_repository=md,
        generation_service=generation,
        judge_service=judge,  # type: ignore[arg-type]
    )
    result = service.answer_text_query(_auth(), 1, "¿requisitos?")
    assert result is not None
    assert judge.calls == []
    assert result.audit_log["score_fidelidad"] is None
    assert "JUDGE:skipped_sample" in result.audit_log["observaciones"]
    assert result.timings_ms["judge"] == 0.0


def test_chat_judge_disabled_does_not_call_judge(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "judge_enabled", False)
    from app.services.config_service import ConfigService

    monkeypatch.setattr(
        ConfigService, "get_bool", lambda self, clave, institucion_id=None, default=False: default
    )
    retrieval_result = _RetrievalResult([_chunk(10, 0.85)])
    generation_result = _GenerationResult(text="Respuesta.")
    conv = FakeConversationsRepository({"id": 1, "external_auth_id": "student-1", "institucion_id": 1})
    messages = FakeMessagesRepository()
    audit = FakeAuditRepository()
    md = FakeMessageDocumentsRepository()
    retrieval = FakeRetrievalService(retrieval_result)
    generation = FakeGenerationService(generation_result)
    judge = FakeJudgeService()
    service = ChatService(
        conversations_repository=conv,
        messages_repository=messages,
        audit_repository=audit,
        feedback_repository=FakeFeedbackRepository(),
        users_repository=FakeUsersRepository(),
        retrieval_service=retrieval,
        message_documents_repository=md,
        generation_service=generation,
        judge_service=judge,  # type: ignore[arg-type]
    )
    result = service.answer_text_query(_auth(), 1, "¿requisitos?")
    assert result is not None
    assert judge.calls == []
    assert result.audit_log["score_fidelidad"] is None
    assert "JUDGE" not in result.audit_log["observaciones"]
    assert result.timings_ms["judge"] == 0.0


def test_chat_uses_institutional_llm_model(monkeypatch) -> None:
    from app.services import chat_service as chat_module
    from app.services.config_service import ConfigService

    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "judge_enabled", False)
    monkeypatch.setattr(
        ConfigService,
        "get_bool",
        lambda self, clave, institucion_id=None, default=False: (
            True if clave == "llm_enabled" else False
        ),
    )
    monkeypatch.setattr(
        ConfigService,
        "get_str",
        lambda self, clave, institucion_id=None, default="": (
            "institucion/modelo-x" if clave == "llm_model" else default
        ),
    )

    instances = []

    class _FakeGenerationService:
        def __init__(self, model=None, temperature=None, max_tokens=None, system_prompt=None):
            self.model = model or settings.llm_model
            self.temperature = (
                temperature if temperature is not None else settings.llm_temperature
            )
            self.max_tokens = max_tokens or settings.llm_max_tokens
            self.system_prompt = system_prompt or "prompt"
            self.calls = []
            instances.append(self)

        def generate(self, query, chunks, history=None):
            self.calls.append((query, chunks, history))
            return _GenerationResult(model=self.model)

    monkeypatch.setattr(chat_module, "GenerationService", _FakeGenerationService)
    service = ChatService(
        conversations_repository=FakeConversationsRepository(None),
        messages_repository=FakeMessagesRepository(),
        audit_repository=FakeAuditRepository(),
        feedback_repository=FakeFeedbackRepository(),
        users_repository=FakeUsersRepository(),
        retrieval_service=FakeRetrievalService(_RetrievalResult([_chunk(10, 0.85)])),
        message_documents_repository=FakeMessageDocumentsRepository(),
        generation_service=None,
        judge_service=FakeJudgeService(),  # type: ignore[arg-type]
    )
    result = service.answer_text_query(_auth(), 1, "¿requisitos?")

    assert result is not None
    used = [instance for instance in instances if instance.calls]
    assert used
    assert used[-1].model == "institucion/modelo-x"
    assert result.assistant_message["modelo_ia"] == "institucion/modelo-x"


def test_chat_uses_institutional_judge_model(monkeypatch) -> None:
    from app.services import chat_service as chat_module
    from app.services.config_service import ConfigService
    from app.services.judge_service import JudgeResult

    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "judge_enabled", True)
    monkeypatch.setattr(settings, "judge_sample_rate", 1.0)
    monkeypatch.setattr(
        ConfigService,
        "get_bool",
        lambda self, clave, institucion_id=None, default=False: (
            True if clave in {"llm_enabled", "judge_enabled"} else default
        ),
    )
    monkeypatch.setattr(
        ConfigService,
        "get_float",
        lambda self, clave, institucion_id=None, default=0.0: (
            1.0 if clave == "judge_sample_rate" else default
        ),
    )
    monkeypatch.setattr(
        ConfigService,
        "get_str",
        lambda self, clave, institucion_id=None, default="": (
            "institucion/juez-x" if clave == "judge_model" else default
        ),
    )

    instances = []

    class _FakeJudgeService:
        def __init__(self, model=None, temperature=None, max_tokens=None):
            self.model = model or settings.judge_model
            self.temperature = (
                temperature if temperature is not None else settings.judge_temperature
            )
            self.max_tokens = max_tokens or settings.judge_max_tokens
            self.calls = []
            instances.append(self)

        def evaluate(self, question, answer, chunks=None):
            self.calls.append((question, answer, chunks))
            return JudgeResult(
                fidelidad=1.0,
                relevancia=1.0,
                contexto=1.0,
                model=self.model,
            )

    monkeypatch.setattr(chat_module, "JudgeService", _FakeJudgeService)
    service = ChatService(
        conversations_repository=FakeConversationsRepository(None),
        messages_repository=FakeMessagesRepository(),
        audit_repository=FakeAuditRepository(),
        feedback_repository=FakeFeedbackRepository(),
        users_repository=FakeUsersRepository(),
        retrieval_service=FakeRetrievalService(_RetrievalResult([_chunk(10, 0.85)])),
        message_documents_repository=FakeMessageDocumentsRepository(),
        generation_service=FakeGenerationService(),
        judge_service=None,
    )
    result = service.answer_text_query(_auth(), 1, "¿requisitos?")

    assert result is not None
    used = [instance for instance in instances if instance.calls]
    assert used
    assert used[-1].model == "institucion/juez-x"
    assert "JUDGE:ok (institucion/juez-x)" in result.audit_log["observaciones"]
