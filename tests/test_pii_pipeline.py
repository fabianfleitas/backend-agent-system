from __future__ import annotations

"""Tests §16 del pipeline PII en el flujo de chat: el LLM/retrieval deben recibir
el texto anonimizado cuando la política está activa, y el flujo debe fallar cerrado
(sin llamadas externas) si el detector no está disponible.

Reutiliza los fakes de tests/test_chat_service.py e inyecta un FakePiiService en
ChatService (ChatService.__init__ acepta pii_service). No requiere Supabase.
"""

from typing import List, Optional

from app.core.config import settings
from app.services.chat_service import (
    ChatService,
    DOMAIN_GUARD_MESSAGE,
    LLM_UNAVAILABLE_MESSAGE,
)
from app.services.pii_service import AnonymizeResult
from tests.test_chat_service import (
    FakeAuditRepository,
    FakeConversationsRepository,
    FakeFeedbackRepository,
    FakeGenerationService,
    FakeMessageDocumentsRepository,
    FakeMessagesRepository,
    FakeRetrievalService,
    FakeUsersRepository,
    _GenerationResult,
    _RetrievalResult,
    _auth,
    _chunk,
)


class FakePiiService:
    def __init__(
        self,
        available: bool = True,
        anonymized_text: str = "[PII_NUMERO_CEDULA_1]",
        error: Optional[str] = None,
    ) -> None:
        self.available = available
        self.anonymized_text = anonymized_text
        self.error = error
        self.anonymize_calls: List[dict] = []
        self.persisted: List[dict] = []

    def anonymize(self, text: str, user_profile: Optional[dict] = None, language: Optional[str] = None) -> AnonymizeResult:
        self.anonymize_calls.append({"text": text, "user_profile": user_profile})
        if not self.available:
            return AnonymizeResult(
                text=text,
                mappings=[],
                detected_count=0,
                available=False,
                error=self.error or "presidio detector unavailable",
            )
        return AnonymizeResult(
            text=self.anonymized_text,
            mappings=[
                {"token": "[PII_NUMERO_CEDULA_1]", "pii_type": "NUMERO_CEDULA", "original_value": "12345678"}
            ],
            detected_count=1,
            available=True,
        )

    def persist_mappings(
        self,
        mappings: List[dict],
        audit_id: str,
        external_auth_id: str,
        institucion_id: Optional[int],
        expires_at=None,
    ) -> List[dict]:
        self.persisted.append(
            {
                "mappings": mappings,
                "audit_id": audit_id,
                "external_auth_id": external_auth_id,
                "institucion_id": institucion_id,
            }
        )
        return mappings


def _make_service(
    pii: FakePiiService,
    retrieval_result=None,
    conversation: Optional[dict] = None,
    generation_result=None,
) -> tuple[ChatService, FakeRetrievalService, FakeGenerationService, FakeMessagesRepository, FakeAuditRepository]:
    conv = FakeConversationsRepository(conversation)
    messages = FakeMessagesRepository()
    audit = FakeAuditRepository()
    md = FakeMessageDocumentsRepository()
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
        pii_service=pii,  # type: ignore[arg-type]
    )
    return service, retrieval, generation, messages, audit


def test_pii_activado_envia_texto_anonimizado_a_llm_y_persiste(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "pii_anonymization_enabled", True)
    pii = FakePiiService(available=True, anonymized_text="[PII_NUMERO_CEDULA_1]")
    service, retrieval, generation, messages, audit = _make_service(
        pii, retrieval_result=_RetrievalResult([_chunk(10, 0.85)])
    )

    result = service.answer_text_query(_auth(), 1, "Mi cédula es 12345678. ¿Requisitos?")

    assert result is not None
    # El texto anonimizado llega al retrieval y al LLM, no el original.
    assert retrieval.calls == ["[PII_NUMERO_CEDULA_1]"]
    assert generation.calls and generation.calls[0][0] == "[PII_NUMERO_CEDULA_1]"
    # El mensaje de usuario y la auditoría guardan la versión anonimizada.
    assert result.user_message["contenido_anonimizado"] == "[PII_NUMERO_CEDULA_1]"
    assert result.user_message["content"] == "Mi cédula es 12345678. ¿Requisitos?"
    assert result.audit_log["pregunta_anonimizada"] == "[PII_NUMERO_CEDULA_1]"
    assert "PII:1" in result.audit_log["observaciones"]
    # Los mappings se persisten con el audit_id.
    assert len(pii.persisted) == 1
    assert pii.persisted[0]["audit_id"] == result.audit_log["id"]
    assert pii.persisted[0]["external_auth_id"] == "student-1"
    assert pii.persisted[0]["institucion_id"] == 1


def test_pii_detector_no_disponible_falla_cerrado_sin_llamadas_externas(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "pii_anonymization_enabled", True)
    pii = FakePiiService(available=False, error="modelo es_core_news_md no instalado")
    service, retrieval, generation, messages, audit = _make_service(pii)

    result = service.answer_text_query(_auth(), 1, "Mi cédula es 12345678. ¿Requisitos?")

    assert result is not None
    # Fail-closed: no se invoca retrieval ni LLM con datos sensibles.
    assert retrieval.calls == []
    assert generation.calls == []
    assert result.response == LLM_UNAVAILABLE_MESSAGE
    assert "PII_UNAVAILABLE" in result.audit_log["observaciones"]
    # El mensaje se guarda raw pero sin contenido anonimizado (no se pudo).
    assert result.user_message["contenido_anonimizado"] is None
    assert pii.persisted == []


def test_pii_desactivado_passthrough_sin_etiqueta(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embeddings_enabled", True)
    monkeypatch.setattr(settings, "llm_enabled", False)
    monkeypatch.setattr(settings, "pii_anonymization_enabled", False)
    pii = FakePiiService(available=True)
    service, retrieval, generation, messages, audit = _make_service(
        pii, retrieval_result=_RetrievalResult([_chunk(10, 0.85)])
    )

    result = service.answer_text_query(_auth(), 1, "¿Requisitos de matrícula?")

    assert result is not None
    # Sin política PII: retrieval recibe el texto original y no hay etiqueta.
    assert retrieval.calls == ["¿Requisitos de matrícula?"]
    assert result.user_message["contenido_anonimizado"] is None
    assert result.audit_log["pregunta_anonimizada"] is None
    assert "PII:" not in result.audit_log["observaciones"]
    assert pii.anonymize_calls == []