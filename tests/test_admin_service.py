from __future__ import annotations

from typing import Optional

from app.services.admin_service import AdminService, _aggregate_ia


class FakeMetricsRepository:
    def __init__(self, **kwargs) -> None:
        self.messages = kwargs.get("messages", [])
        self.conversations = kwargs.get("conversations", [])
        self.documents = kwargs.get("documents", [])
        self.feedbacks = kwargs.get("feedbacks", [])
        self.audit_logs = kwargs.get("audit_logs", [])
        self.message_documents = kwargs.get("message_documents", [])

    def list_messages(self, institucion_id=None):
        return list(self.messages)

    def list_conversations(self, institucion_id=None):
        return list(self.conversations)

    def list_documents(self, institucion_id=None):
        return list(self.documents)

    def list_feedbacks(self, institucion_id=None):
        return list(self.feedbacks)

    def list_audit_logs(self, institucion_id=None):
        return list(self.audit_logs)

    def list_message_documents(self, institucion_id=None):
        return list(self.message_documents)


class FakeUsersRepository:
    def list_users(self, institucion_id=None):
        return []


def _audit(observaciones: str, modelo_ia: str | None = None, tokens_in: int = 0, tokens_out: int = 0, t_ms: float | None = None) -> dict:
    return {
        "observaciones": observaciones,
        "modelo_ia": modelo_ia,
        "tokens_input": tokens_in,
        "tokens_output": tokens_out,
        "tiempo_respuesta_ms": t_ms,
    }


def _make_service(**kwargs) -> AdminService:
    return AdminService(
        users_repository=FakeUsersRepository(),
        metrics_repository=FakeMetricsRepository(**kwargs),
    )


def test_aggregate_ia_counts_outcomes_and_rates() -> None:
    audits = [
        _audit("LLM: OpenRouter (contexto RAG) [text]"),
        _audit("LLM: OpenRouter (contexto RAG) [voice]"),
        _audit("GUARD: sin contexto [text]"),
        _audit("LLM_FAILED: timeout [text]"),
        _audit("MOCK: sin evaluación automática [text]"),
    ]
    result = _aggregate_ia(audits, [])
    assert result["total_llm_responses"] == 2
    assert result["total_guard"] == 1
    assert result["total_llm_failed"] == 1
    assert result["guard_rate"] == 0.25
    assert result["llm_failed_rate"] == 0.25
    assert result["total_voice_queries"] == 1
    assert result["total_text_queries"] == 4


def test_aggregate_ia_rates_exclude_mocks_from_denominator() -> None:
    audits = [
        _audit("GUARD: sin contexto [text]"),
        _audit("MOCK: sin evaluación automática [text]"),
        _audit("RETRIEVAL: contexto recuperado [text]"),
    ]
    result = _aggregate_ia(audits, [])
    assert result["total_llm_responses"] == 0
    assert result["total_guard"] == 1
    assert result["guard_rate"] == 1.0
    assert result["llm_failed_rate"] == 0.0


def test_aggregate_ia_zero_denominator_returns_zero_rates() -> None:
    result = _aggregate_ia([], [])
    assert result["total_llm_responses"] == 0
    assert result["guard_rate"] == 0.0
    assert result["llm_failed_rate"] == 0.0
    assert result["avg_retrieval_similarity"] == 0.0
    assert result["tokens_by_model"] == {}


def test_aggregate_ia_tokens_by_model() -> None:
    audits = [
        _audit("LLM: ... [text]", modelo_ia="openai/gpt-4o-mini", tokens_in=100, tokens_out=50),
        _audit("LLM: ... [text]", modelo_ia="openai/gpt-4o-mini", tokens_in=200, tokens_out=80),
        _audit("LLM: ... [voice]", modelo_ia="anthropic/claude", tokens_in=40, tokens_out=10),
    ]
    result = _aggregate_ia(audits, [])
    assert result["total_tokens_input"] == 340
    assert result["total_tokens_output"] == 140
    assert result["tokens_by_model"] == {
        "openai/gpt-4o-mini": {"input": 300, "output": 130},
        "anthropic/claude": {"input": 40, "output": 10},
    }


def test_aggregate_ia_avg_retrieval_similarity() -> None:
    docs = [{"similarity_score": 0.80}, {"similarity_score": 0.60}, {"similarity_score": None}]
    result = _aggregate_ia([], docs)
    assert result["avg_retrieval_similarity"] == 0.7


def test_aggregate_ia_channel_response_times() -> None:
    audits = [
        _audit("LLM: ... [voice]", t_ms=2000.0),
        _audit("LLM: ... [voice]", t_ms=3000.0),
        _audit("LLM: ... [text]", t_ms=800.0),
        _audit("LLM: ... [text]", t_ms=1200.0),
    ]
    result = _aggregate_ia(audits, [])
    assert result["avg_response_time_voice"] == 2500.0
    assert result["avg_response_time_text"] == 1000.0


def test_metrics_out_builds_full_response() -> None:
    service = _make_service(
        messages=[{"id": 1, "tiempo_respuesta_ms": 500.0, "rol_mensaje": "ASSISTANT"}],
        conversations=[{"id": 1}],
        documents=[{"id": 1}],
        feedbacks=[{"id": 1}],
        audit_logs=[_audit("LLM: ... [text]", modelo_ia="openai/gpt-4o-mini", tokens_in=100, tokens_out=50, t_ms=900.0)],
        message_documents=[{"similarity_score": 0.85}],
    )
    metrics = service.get_metrics(auth=None)
    assert metrics.total_queries == 1
    assert metrics.total_conversations == 1
    assert metrics.total_documents == 1
    assert metrics.total_feedbacks == 1
    assert metrics.total_llm_responses == 1
    assert metrics.total_text_queries == 1
    assert metrics.tokens_by_model == {"openai/gpt-4o-mini": {"input": 100, "output": 50}}
    assert metrics.avg_retrieval_similarity == 0.85
    assert metrics.avg_response_time == 500.0


def test_metrics_empty_returns_defaults() -> None:
    service = _make_service()
    metrics = service.get_metrics(auth=None)
    assert metrics.total_queries == 0
    assert metrics.total_llm_responses == 0
    assert metrics.guard_rate == 0.0
    assert metrics.tokens_by_model == {}
    assert metrics.system_status == "healthy"