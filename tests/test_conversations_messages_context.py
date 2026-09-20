from __future__ import annotations

"""Tests para sources/rating en mensajes de conversación (GET messages / detail)."""

from app.services.conversations_service import ConversationsService


class FakeMessagesRepo:
    def get_conversation_messages(self, conversation_id):
        return [
            {
                "id": 1,
                "conversacion_id": conversation_id,
                "rol_mensaje": "ASSISTANT",
                "contenido_texto": "respuesta",
                "fecha_envio": "2026-01-01T00:00:00Z",
            },
            {
                "id": 2,
                "conversacion_id": conversation_id,
                "rol_mensaje": "USER",
                "contenido_texto": "pregunta",
                "fecha_envio": "2026-01-01T00:00:01Z",
            },
        ]


class FakeMessageDocumentsRepo:
    def get_sources_by_message_ids(self, message_ids):
        return [
            {"mensaje_id": 1, "documento_id": 10, "page_number": 3, "similarity_score": 0.9},
            {"mensaje_id": 1, "documento_id": 11, "page_number": 1, "similarity_score": 0.7},
        ]

    def get_document_titles(self, document_ids):
        return {10: "Reglamento", 11: "Manual"}


class FakeFeedbackRepo:
    def get_feedback_by_message_ids(self, message_ids):
        return [{"message_id": 1, "rating": 5, "comment": "Excelente"}]


def test_get_messages_enriches_sources_and_rating():
    service = ConversationsService(
        messages_repository=FakeMessagesRepo(),
        message_documents_repository=FakeMessageDocumentsRepo(),
        feedback_repository=FakeFeedbackRepo(),
    )
    messages = service.get_messages(1)
    assert len(messages) == 2

    assistant = messages[0]
    assert len(assistant["_sources"]) == 2
    assert assistant["_sources"][0]["document"] == "Reglamento"
    assert assistant["_sources"][0]["page"] == 3
    assert assistant["_sources"][1]["document"] == "Manual"
    assert assistant["_rating"] == 5
    assert assistant["_feedback_comment"] == "Excelente"

    user = messages[1]
    assert user["_sources"] == []
    assert user["_rating"] is None


def test_get_messages_without_context_returns_plain_messages():
    class EmptyMDRepo:
        def get_sources_by_message_ids(self, message_ids):
            return []

        def get_document_titles(self, document_ids):
            return {}

    class EmptyFBRepo:
        def get_feedback_by_message_ids(self, message_ids):
            return []

    service = ConversationsService(
        messages_repository=FakeMessagesRepo(),
        message_documents_repository=EmptyMDRepo(),
        feedback_repository=EmptyFBRepo(),
    )
    messages = service.get_messages(1)
    assert messages[0]["_sources"] == []
    assert messages[0]["_rating"] is None