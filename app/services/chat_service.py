from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from app.core.security import AuthContext
from app.repositories.audit_repository import AuditRepository
from app.repositories.conversations_repository import ConversationsRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.messages_repository import MessagesRepository
from app.repositories.users_repository import UsersRepository


@dataclass
class ChatResult:
    conversation_id: int
    user_message: dict
    response: str
    assistant_message: dict
    audit_log: dict
    elapsed_ms: float


class ChatService:
    def __init__(
        self,
        conversations_repository: Optional[ConversationsRepository] = None,
        messages_repository: Optional[MessagesRepository] = None,
        audit_repository: Optional[AuditRepository] = None,
        feedback_repository: Optional[FeedbackRepository] = None,
        users_repository: Optional[UsersRepository] = None,
    ) -> None:
        self.conversations_repository = conversations_repository or ConversationsRepository()
        self.messages_repository = messages_repository or MessagesRepository()
        self.audit_repository = audit_repository or AuditRepository()
        self.feedback_repository = feedback_repository or FeedbackRepository()
        self.users_repository = users_repository or UsersRepository()

    def get_owned_conversation(self, conversation_id: int, external_auth_id: str) -> Optional[dict]:
        conversation = self.conversations_repository.get_conversation(conversation_id)
        if not conversation or conversation.get("external_auth_id") != external_auth_id:
            return None
        return conversation

    def answer_text_query(self, auth: AuthContext, conversation_id: int, message: str) -> Optional[ChatResult]:
        self.users_repository.get_or_create_user(auth)
        conversation = self.get_owned_conversation(conversation_id, auth.external_auth_id)
        if not conversation:
            return None

        user_message = self.messages_repository.create_message(
            conversation_id=conversation_id,
            external_auth_id=auth.external_auth_id,
            role="USER",
            content=message,
        )

        start = time.perf_counter()
        answer = f"MOCK: Recibí tu consulta institucional: {message}"
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        tokens_input = len(message.split())
        tokens_output = len(answer.split())
        assistant_msg = self.messages_repository.create_message(
            conversation_id=conversation_id,
            external_auth_id=auth.external_auth_id,
            role="ASSISTANT",
            content=answer,
            proveedor_ia="OpenRouter",
            modelo_ia="mock",
            temperatura=0.2,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tiempo_respuesta_ms=elapsed_ms,
        )

        audit_log = self.audit_repository.create_audit_log(
            conversation_id=conversation_id,
            message_id=assistant_msg["id"],
            external_auth_id=auth.external_auth_id,
            pregunta_original=message,
            respuesta_texto=answer,
            proveedor_ia="OpenRouter",
            modelo_ia="mock",
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tiempo_respuesta_ms=elapsed_ms,
            observaciones="MOCK: sin evaluación automática",
        )
        assistant_msg = (
            self.messages_repository.update_message_audit_id(assistant_msg["id"], audit_log["id"])
            or assistant_msg
        )
        self.conversations_repository.touch_conversation(conversation_id)
        return ChatResult(
            conversation_id=conversation_id,
            user_message=user_message,
            response=answer,
            assistant_message=assistant_msg,
            audit_log=audit_log,
            elapsed_ms=elapsed_ms,
        )

    def answer_voice_query(
        self,
        auth: AuthContext,
        conversation_id: int,
        transcription: str,
    ) -> Optional[ChatResult]:
        self.users_repository.get_or_create_user(auth)
        conversation = self.get_owned_conversation(conversation_id, auth.external_auth_id)
        if not conversation:
            return None

        user_message = self.messages_repository.create_message(
            conversation_id=conversation_id,
            external_auth_id=auth.external_auth_id,
            role="USER",
            content=transcription,
        )

        start = time.perf_counter()
        answer = "MOCK: respuesta simulada basada en reglamentos institucionales (RAG aún no implementado)"
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        tokens_input = len(transcription.split())
        tokens_output = len(answer.split())
        assistant_msg = self.messages_repository.create_message(
            conversation_id=conversation_id,
            external_auth_id=auth.external_auth_id,
            role="ASSISTANT",
            content=answer,
            proveedor_ia="OpenRouter",
            modelo_ia="mock",
            temperatura=0.2,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tiempo_respuesta_ms=elapsed_ms,
        )

        audit_log = self.audit_repository.create_audit_log(
            conversation_id=conversation_id,
            message_id=assistant_msg["id"],
            external_auth_id=auth.external_auth_id,
            pregunta_original=transcription,
            respuesta_texto=answer,
            proveedor_ia="OpenRouter",
            modelo_ia="mock",
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tiempo_respuesta_ms=elapsed_ms,
            observaciones="MOCK: sin evaluación automática",
        )
        assistant_msg = (
            self.messages_repository.update_message_audit_id(assistant_msg["id"], audit_log["id"])
            or assistant_msg
        )
        self.conversations_repository.touch_conversation(conversation_id)
        return ChatResult(
            conversation_id=conversation_id,
            user_message=user_message,
            response=answer,
            assistant_message=assistant_msg,
            audit_log=audit_log,
            elapsed_ms=elapsed_ms,
        )

    def create_feedback(
        self,
        auth: AuthContext,
        message_id: int,
        rating: int,
        comment: Optional[str],
        audit_id: str,
    ) -> Optional[dict]:
        self.users_repository.get_or_create_user(auth)
        message = self.messages_repository.get_message(message_id)
        if not message or message.get("external_auth_id") != auth.external_auth_id:
            return None
        return self.feedback_repository.create_feedback(
            message_id=message_id,
            rating=rating,
            comment=comment,
            audit_id=audit_id,
            external_auth_id=auth.external_auth_id,
        )
