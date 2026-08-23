from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import settings
from app.core.security import AuthContext
from app.repositories.audit_repository import AuditRepository
from app.repositories.conversations_repository import ConversationsRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.messages_repository import MessagesRepository
from app.repositories.message_documents_repository import MessageDocumentsRepository
from app.repositories.users_repository import UsersRepository
from app.services.generation_service import GenerationService
from app.services.retrieval_service import RetrievalService
from app.utils.tokens import count_tokens

logger = logging.getLogger(__name__)

DOMAIN_GUARD_MESSAGE = (
    "No tengo información institucional suficiente para responder esa consulta. "
    "Por favor, reformule su pregunta dentro del ámbito académico institucional."
)

LLM_UNAVAILABLE_MESSAGE = (
    "No fue posible generar la respuesta en este momento. Intenta nuevamente."
)


@dataclass
class ChatResult:
    conversation_id: int
    user_message: dict
    response: str
    assistant_message: dict
    audit_log: dict
    elapsed_ms: float
    sources: List[dict] = field(default_factory=list)


class ChatService:
    def __init__(
        self,
        conversations_repository: Optional[ConversationsRepository] = None,
        messages_repository: Optional[MessagesRepository] = None,
        audit_repository: Optional[AuditRepository] = None,
        feedback_repository: Optional[FeedbackRepository] = None,
        users_repository: Optional[UsersRepository] = None,
        retrieval_service: Optional[RetrievalService] = None,
        message_documents_repository: Optional[MessageDocumentsRepository] = None,
        generation_service: Optional[GenerationService] = None,
    ) -> None:
        self.conversations_repository = conversations_repository or ConversationsRepository()
        self.messages_repository = messages_repository or MessagesRepository()
        self.audit_repository = audit_repository or AuditRepository()
        self.feedback_repository = feedback_repository or FeedbackRepository()
        self.users_repository = users_repository or UsersRepository()
        self.retrieval_service = retrieval_service or RetrievalService()
        self.message_documents_repository = message_documents_repository or MessageDocumentsRepository()
        self.generation_service = generation_service or GenerationService()

    def get_owned_conversation(self, conversation_id: int, external_auth_id: str) -> Optional[dict]:
        conversation = self.conversations_repository.get_conversation(conversation_id)
        if not conversation or conversation.get("external_auth_id") != external_auth_id:
            return None
        return conversation

    def answer_text_query(self, auth: AuthContext, conversation_id: int, message: str) -> Optional[ChatResult]:
        return self._answer_query(auth, conversation_id, message, origin="text")

    def answer_voice_query(
        self,
        auth: AuthContext,
        conversation_id: int,
        transcription: str,
    ) -> Optional[ChatResult]:
        if not settings.stt_enabled:
            return self._answer_voice_mock(auth, conversation_id, transcription)
        return self._answer_query(auth, conversation_id, transcription, origin="voice")

    def _answer_query(
        self,
        auth: AuthContext,
        conversation_id: int,
        message: str,
        origin: str,
    ) -> Optional[ChatResult]:
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
        retrieved = self.retrieval_service.retrieve(message) if settings.embeddings_enabled else None
        embedding_model = None
        modelo_ia = "mock"
        tokens_input: Optional[int] = None
        tokens_output: Optional[int] = None
        sources: List[dict] = []
        if retrieved is not None and not retrieved.ok:
            logger.warning(
                "Retrieval failed falling back to mock conversation_id=%s error=%s",
                conversation_id,
                retrieved.error,
            )
            answer = f"MOCK: Recibí tu consulta institucional: {message}"
            observaciones = f"MOCK: sin evaluación automática [{origin}]"
            tokens_input = len(message.split())
            tokens_output = len(answer.split())
        elif retrieved is not None and retrieved.ok and not retrieved.chunks:
            answer = DOMAIN_GUARD_MESSAGE
            observaciones = f"GUARD: sin contexto institucional recuperado [{origin}]"
            tokens_input = len(message.split())
            tokens_output = len(answer.split())
        elif retrieved is not None and retrieved.ok:
            embedding_model = settings.embedding_model
            sources = [
                {
                    "document_id": chunk.document_id,
                    "document": chunk.document_title,
                    "page": chunk.page_number,
                    "similarity_score": min(1.0, max(0.0, chunk.similarity)),
                }
                for chunk in retrieved.chunks
            ]
            if settings.llm_enabled:
                history = self._build_history(conversation_id, exclude_id=user_message["id"])
                generation = self.generation_service.generate(
                    message, retrieved.chunks, history=history
                )
                if generation.ok:
                    answer = generation.text
                    modelo_ia = generation.model
                    tokens_input = generation.tokens_input
                    tokens_output = generation.tokens_output
                    observaciones = f"LLM: OpenRouter (contexto RAG) [{origin}]"
                else:
                    logger.error(
                        "LLM generation failed conversation_id=%s model=%s error=%s",
                        conversation_id,
                        settings.llm_model,
                        generation.error,
                    )
                    answer = LLM_UNAVAILABLE_MESSAGE
                    modelo_ia = settings.llm_model
                    observaciones = f"LLM_FAILED: {generation.error} [{origin}]"
            else:
                preview = retrieved.chunks[0].chunk_text[:200]
                answer = (
                    f"MOCK: Recuperé {retrieved.total} fragmentos relevantes. "
                    f"Primer fragmento: {preview} "
                    f"(respuesta real pendiente de OpenRouter)."
                )
                modelo_ia = "mock-retrieval"
                observaciones = f"RETRIEVAL: contexto recuperado; respuesta pendiente de OpenRouter [{origin}]"
                tokens_input = len(message.split())
                tokens_output = len(answer.split())
        else:
            answer = f"MOCK: Recibí tu consulta institucional: {message}"
            observaciones = f"MOCK: sin evaluación automática [{origin}]"
            tokens_input = len(message.split())
            tokens_output = len(answer.split())
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assistant_msg = self.messages_repository.create_message(
            conversation_id=conversation_id,
            external_auth_id=auth.external_auth_id,
            role="ASSISTANT",
            content=answer,
            proveedor_ia="OpenRouter",
            modelo_ia=modelo_ia,
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
            modelo_ia=assistant_msg.get("modelo_ia") or "mock",
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tiempo_respuesta_ms=elapsed_ms,
            observaciones=observaciones,
            embedding_model=embedding_model,
        )
        assistant_msg = (
            self.messages_repository.update_message_audit_id(assistant_msg["id"], audit_log["id"])
            or assistant_msg
        )
        if sources:
            try:
                traceability_rows = [
                    {
                        "mensaje_id": assistant_msg["id"],
                        "audit_id": audit_log["id"],
                        "documento_id": source["document_id"],
                        "documento_version_id": chunk.document_version_id,
                        "chunk_id": chunk.chunk_id,
                        "similarity_score": source["similarity_score"],
                        "page_number": chunk.page_number,
                    }
                    for source, chunk in zip(sources, retrieved.chunks)
                ]
                self.message_documents_repository.insert_message_documents(traceability_rows)
            except Exception as exc:
                logger.warning(
                    "Message_documents persist failed conversation_id=%s error=%s",
                    conversation_id,
                    exc,
                )
        self.conversations_repository.touch_conversation(conversation_id)
        return ChatResult(
            conversation_id=conversation_id,
            user_message=user_message,
            response=answer,
            assistant_message=assistant_msg,
            audit_log=audit_log,
            elapsed_ms=elapsed_ms,
            sources=sources,
        )

    def _build_history(
        self,
        conversation_id: int,
        exclude_id: int,
    ) -> List[dict]:
        if not settings.llm_history_enabled:
            return []
        messages = self.messages_repository.get_conversation_messages(conversation_id)
        history: List[tuple[int, str, str]] = []
        for row in messages:
            role = row.get("rol_mensaje")
            content = row.get("contenido_texto")
            if role not in ("USER", "ASSISTANT") or not content:
                continue
            if int(row["id"]) == exclude_id:
                continue
            if role == "ASSISTANT" and content == LLM_UNAVAILABLE_MESSAGE:
                continue
            history.append((int(row["id"]), role, content))

        budget = 0
        selected: List[tuple[int, str, str]] = []
        for message_id, role, content in reversed(history):
            budget += count_tokens(content)
            if budget > settings.llm_history_max_tokens or len(selected) >= settings.llm_history_max_messages:
                break
            selected.append((message_id, role, content))
        selected.reverse()

        return [
            {"role": "user" if role == "USER" else "assistant", "content": content}
            for _, role, content in selected
        ]

    def _answer_voice_mock(
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
        answer = "MOCK: respuesta simulada basada en reglamentos institucionales (voz sin STT real)"
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
            observaciones="MOCK: sin evaluación automática [voice]",
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
            sources=[],
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
