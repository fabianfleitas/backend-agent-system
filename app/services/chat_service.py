from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import settings
from app.services.config_service import ConfigService
from app.core.security import AuthContext
from app.repositories.audit_repository import AuditRepository
from app.repositories.conversations_repository import ConversationsRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.messages_repository import MessagesRepository
from app.repositories.message_documents_repository import MessageDocumentsRepository
from app.repositories.users_repository import UsersRepository
from app.services.generation_service import GenerationService
from app.services.handoff_service import HandoffService
from app.services.judge_service import JudgeService
from app.services.pii_service import PiiService
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
    timings_ms: dict[str, float] = field(default_factory=dict)


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
        pii_service: Optional[PiiService] = None,
        judge_service: Optional[JudgeService] = None,
        handoff_service: Optional[HandoffService] = None,
    ) -> None:
        self.conversations_repository = conversations_repository or ConversationsRepository()
        self.messages_repository = messages_repository or MessagesRepository()
        self.audit_repository = audit_repository or AuditRepository()
        self.feedback_repository = feedback_repository or FeedbackRepository()
        self.users_repository = users_repository or UsersRepository()
        self.retrieval_service = retrieval_service or RetrievalService()
        self.message_documents_repository = message_documents_repository or MessageDocumentsRepository()
        self.generation_service = generation_service or GenerationService()
        self.pii_service = pii_service or PiiService()
        self.judge_service = judge_service or JudgeService()
        self._generation_service_injected = generation_service is not None
        self._judge_service_injected = judge_service is not None
        self.handoff_service = handoff_service or HandoffService()

    def get_owned_conversation(self, conversation_id: int, external_auth_id: str, institucion_id: int = None) -> Optional[dict]:
        conversation = self.conversations_repository.get_conversation(conversation_id, institucion_id=institucion_id)
        if not conversation or conversation.get("external_auth_id") != external_auth_id:
            return None
        # Si se pasó institucion_id y el recurso pertenece a otra, ya filtrado por repo; 
        # si no coincide el external_auth_id, es 404 (no existe para este usuario/institución)
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
        service_started = time.perf_counter()
        timings_ms: dict[str, float] = {}
        phase_started = time.perf_counter()
        user = self.users_repository.get_or_create_user(auth)
        timings_ms["user_lookup"] = (time.perf_counter() - phase_started) * 1000.0
        from fastapi import HTTPException
        if auth.institucion_id is None and not auth.is_platform_admin:
            raise HTTPException(status_code=403, detail="Institution membership required")
        conversation = self.get_owned_conversation(conversation_id, auth.external_auth_id, auth.institucion_id)
        if not conversation:
            return None

        phase_started = time.perf_counter()
        config = ConfigService()
        pii_enabled = config.get_bool(
            "pii_anonymization_enabled",
            auth.institucion_id,
            settings.pii_anonymization_enabled,
        )
        timings_ms["config_lookup"] = (time.perf_counter() - phase_started) * 1000.0
        query_text = message
        contenido_anonimizado: Optional[str] = None
        pending_mappings: List[dict] = []
        pii_count = 0
        pii_fail_closed = False
        pii_result = None
        phase_started = time.perf_counter()
        if pii_enabled:
            pii_result = self.pii_service.anonymize(
                message,
                user_profile={
                    "full_name": (user or {}).get("full_name"),
                    "email": (user or {}).get("email"),
                },
            )
            if pii_result.available:
                query_text = pii_result.text
                contenido_anonimizado = pii_result.text
                pending_mappings = pii_result.mappings
                pii_count = pii_result.detected_count
            else:
                pii_fail_closed = True
                logger.warning(
                    "PII policy enabled but detector unavailable; external calls skipped conversation_id=%s",
                    conversation_id,
                )
        timings_ms["pii"] = (time.perf_counter() - phase_started) * 1000.0

        phase_started = time.perf_counter()
        user_message = self.messages_repository.create_message(
            conversation_id=conversation_id,
            external_auth_id=auth.external_auth_id,
            role="USER",
            content=message,
            contenido_anonimizado=contenido_anonimizado,
        )
        timings_ms["user_message_persistence"] = (time.perf_counter() - phase_started) * 1000.0

        start = time.perf_counter()
        embedding_model = None
        modelo_ia = "mock"
        tokens_input: Optional[int] = None
        tokens_output: Optional[int] = None
        score_fidelidad: Optional[float] = None
        score_relevancia: Optional[float] = None
        score_contexto: Optional[float] = None
        handoff_motivo: Optional[str] = None
        handoff_resumen: Optional[str] = None
        sources: List[dict] = []
        retrieved = None
        timings_ms["retrieval"] = 0.0
        timings_ms["generation"] = 0.0
        timings_ms["judge"] = 0.0
        judge_enabled = False
        if pii_fail_closed:
            answer = LLM_UNAVAILABLE_MESSAGE
            observaciones = f"PII_UNAVAILABLE: {pii_result.error} [{origin}]"
            tokens_input = len(query_text.split())
            tokens_output = len(answer.split())
        else:
            retrieval_started = time.perf_counter()
            retrieved = self.retrieval_service.retrieve(query_text, auth.institucion_id) if settings.embeddings_enabled else None
            timings_ms["retrieval"] = (time.perf_counter() - retrieval_started) * 1000.0
            if retrieved is not None and not retrieved.ok:
                logger.warning(
                    "Retrieval failed falling back to mock conversation_id=%s error=%s",
                    conversation_id,
                    retrieved.error,
                )
                answer = f"MOCK: Recibí tu consulta institucional: {message}"
                observaciones = f"MOCK: sin evaluación automática [{origin}]"
                tokens_input = len(query_text.split())
                tokens_output = len(answer.split())
            elif retrieved is not None and retrieved.ok and not retrieved.chunks:
                answer = DOMAIN_GUARD_MESSAGE
                observaciones = f"GUARD: sin contexto institucional recuperado [{origin}]"
                tokens_input = len(query_text.split())
                tokens_output = len(answer.split())
                handoff_motivo = self.handoff_service.should_escalate(
                    message,
                    institucion_id=auth.institucion_id,
                    guard_triggered=True,
                )
                if handoff_motivo:
                    handoff_resumen = message
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
                config_started = time.perf_counter()
                llm_enabled = config.get_bool("llm_enabled", auth.institucion_id, settings.llm_enabled)
                generation_service = (
                    self._generation_service_for(config, auth.institucion_id)
                    if llm_enabled
                    else self.generation_service
                )
                timings_ms["llm_config"] = (time.perf_counter() - config_started) * 1000.0
                if llm_enabled:
                    history = self._build_history(conversation_id, exclude_id=user_message["id"])
                    generation_started = time.perf_counter()
                    generation = generation_service.generate(
                        query_text, retrieved.chunks, history=history
                    )
                    timings_ms["generation"] = (time.perf_counter() - generation_started) * 1000.0
                    if generation.ok:
                        answer = generation.text
                        modelo_ia = generation.model
                        tokens_input = generation.tokens_input
                        tokens_output = generation.tokens_output
                        observaciones = f"LLM: OpenRouter (contexto RAG) [{origin}]"
                        judge_config_started = time.perf_counter()
                        judge_enabled = config.get_bool(
                            "judge_enabled", auth.institucion_id, settings.judge_enabled
                        )
                        timings_ms["judge_config"] = (
                            time.perf_counter() - judge_config_started
                        ) * 1000.0
                        if judge_enabled and self._judge_selected_for_sampling(
                            config, auth.institucion_id
                        ):
                            judge_service = self._judge_service_for(config, auth.institucion_id)
                            judge_started = time.perf_counter()
                            judge = judge_service.evaluate(
                                question=query_text,
                                answer=answer,
                                chunks=retrieved.chunks,
                            )
                            timings_ms["judge"] = (time.perf_counter() - judge_started) * 1000.0
                            if judge.ok:
                                score_fidelidad = judge.fidelidad
                                score_relevancia = judge.relevancia
                                score_contexto = judge.contexto
                                observaciones = f"{observaciones} | JUDGE:ok ({judge.model})"
                            else:
                                observaciones = f"{observaciones} | JUDGE_FAILED: {judge.error}"
                        elif judge_enabled:
                            observaciones = f"{observaciones} | JUDGE:skipped_sample"
                    else:
                        logger.error(
                            "LLM generation failed conversation_id=%s model=%s error=%s",
                            conversation_id,
                            generation.model,
                            generation.error,
                        )
                        answer = LLM_UNAVAILABLE_MESSAGE
                        modelo_ia = generation.model
                        observaciones = f"LLM_FAILED: {generation.error} [{origin}]"
                        handoff_motivo = self.handoff_service.should_escalate(
                            message,
                            institucion_id=auth.institucion_id,
                            llm_failed=True,
                        )
                        if handoff_motivo:
                            handoff_resumen = f"Fallo del modelo: {generation.error}"
                else:
                    preview = retrieved.chunks[0].chunk_text[:200]
                    answer = (
                        f"MOCK: Recuperé {retrieved.total} fragmentos relevantes. "
                        f"Primer fragmento: {preview} "
                        f"(respuesta real pendiente de OpenRouter)."
                    )
                    modelo_ia = "mock-retrieval"
                    observaciones = f"RETRIEVAL: contexto recuperado; respuesta pendiente de OpenRouter [{origin}]"
                    tokens_input = len(query_text.split())
                    tokens_output = len(answer.split())
            else:
                answer = f"MOCK: Recibí tu consulta institucional: {message}"
                observaciones = f"MOCK: sin evaluación automática [{origin}]"
                tokens_input = len(query_text.split())
                tokens_output = len(answer.split())
        if pii_enabled and not pii_fail_closed:
            observaciones = f"{observaciones} | PII:{pii_count}"
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        deanon_count = 0
        if pii_enabled and not pii_fail_closed and pending_mappings:
            restored = self.pii_service.restore(answer, pending_mappings)
            if restored != answer:
                answer = restored
                deanon_count = len(pending_mappings)
                observaciones = f"{observaciones} | DEANON:{deanon_count}"

        if not handoff_motivo:
            handoff_motivo = self.handoff_service.should_escalate(
                message,
                institucion_id=auth.institucion_id,
            )
            if handoff_motivo:
                handoff_resumen = message

        phase_started = time.perf_counter()
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
            pregunta_anonimizada=contenido_anonimizado,
            respuesta_texto=answer,
            proveedor_ia="OpenRouter",
            modelo_ia=assistant_msg.get("modelo_ia") or "mock",
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tiempo_respuesta_ms=elapsed_ms,
            observaciones=observaciones,
            embedding_model=embedding_model,
            institucion_id=auth.institucion_id,
            score_fidelidad=score_fidelidad,
            score_relevancia=score_relevancia,
            score_contexto=score_contexto,
        )
        assistant_msg = (
            self.messages_repository.update_message_audit_id(assistant_msg["id"], audit_log["id"])
            or assistant_msg
        )
        if pending_mappings:
            self.pii_service.persist_mappings(
                pending_mappings,
                audit_id=audit_log["id"],
                external_auth_id=auth.external_auth_id,
                institucion_id=auth.institucion_id,
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
        if handoff_motivo:
            try:
                escalation = self.handoff_service.create_escalation(
                    institucion_id=auth.institucion_id,
                    conversacion_id=conversation_id,
                    mensaje_id=assistant_msg["id"],
                    audit_id=audit_log["id"],
                    external_auth_id=auth.external_auth_id,
                    motivo=handoff_motivo,
                    resumen=handoff_resumen or "",
                )
                if escalation:
                    new_obs = f"{observaciones} | HANDOFF:{handoff_motivo}"
                    self.audit_repository.update_observaciones(audit_log["id"], new_obs)
                    audit_log["observaciones"] = new_obs
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Escalation creation failed conversation_id=%s error=%s",
                    conversation_id,
                    exc,
                )
        self.conversations_repository.touch_conversation(conversation_id)
        timings_ms["persistence_and_handoff"] = (time.perf_counter() - phase_started) * 1000.0
        timings_ms["service_total"] = (time.perf_counter() - service_started) * 1000.0
        logger.info(
            "chat_timing conversation_id=%s audit_id=%s origin=%s judge_enabled=%s "
            "timings_ms=%s pipeline_ms=%.1f",
            conversation_id,
            audit_log.get("id"),
            origin,
            judge_enabled,
            {key: round(value, 1) for key, value in timings_ms.items()},
            elapsed_ms,
        )
        return ChatResult(
            conversation_id=conversation_id,
            user_message=user_message,
            response=answer,
            assistant_message=assistant_msg,
            audit_log=audit_log,
            elapsed_ms=elapsed_ms,
            sources=sources,
            timings_ms=timings_ms,
        )

    def regenerate(self, auth: AuthContext, conversation_id: int) -> Optional[dict]:
        """Regenera la última respuesta del asistente reemplazándola in-place (S11).

        Reutiliza el último turno (USER + ASSISTANT) y re-ejecuta el pipeline
        (RAG + LLM + judge). No agrega un turno nuevo: actualiza el mensaje del
        asistente y crea un nuevo `audit_log`.
        """
        self.users_repository.get_or_create_user(auth)
        conversation = self.get_owned_conversation(conversation_id, auth.external_auth_id, auth.institucion_id)
        if not conversation:
            return None

        messages = self.messages_repository.get_conversation_messages(conversation_id)
        assistant_idx: Optional[int] = None
        last_assistant: Optional[dict] = None
        for i, m in enumerate(messages):
            if m.get("rol_mensaje") == "ASSISTANT":
                last_assistant = m
                assistant_idx = i
        if last_assistant is None or assistant_idx is None:
            return None

        user_msg: Optional[dict] = None
        for m in reversed(messages[:assistant_idx]):
            if m.get("rol_mensaje") == "USER":
                user_msg = m
                break
        if user_msg is None:
            return None

        config = ConfigService()
        pii_enabled = config.get_bool(
            "pii_anonymization_enabled",
            auth.institucion_id,
            settings.pii_anonymization_enabled,
        )
        query_text = user_msg.get("contenido_anonimizado") or user_msg.get("contenido_texto") or ""

        start = time.perf_counter()
        embedding_model = None
        modelo_ia = "mock"
        tokens_input: Optional[int] = None
        tokens_output: Optional[int] = None
        score_fidelidad: Optional[float] = None
        score_relevancia: Optional[float] = None
        score_contexto: Optional[float] = None
        sources: List[dict] = []
        answer: Optional[str] = None
        observaciones = ""

        if settings.embeddings_enabled:
            retrieved = self.retrieval_service.retrieve(query_text, auth.institucion_id)
            if retrieved is not None and retrieved.ok and retrieved.chunks:
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
                if config.get_bool("llm_enabled", auth.institucion_id, settings.llm_enabled):
                    history = self._build_history(conversation_id, exclude_id=user_msg["id"])
                    generation_service = self._generation_service_for(config, auth.institucion_id)
                    generation = generation_service.generate(query_text, retrieved.chunks, history=history)
                    if generation.ok:
                        answer = generation.text
                        modelo_ia = generation.model
                        tokens_input = generation.tokens_input
                        tokens_output = generation.tokens_output
                        observaciones = "LLM: OpenRouter (contexto RAG) [regenerate]"
                        if config.get_bool("judge_enabled", auth.institucion_id, settings.judge_enabled):
                            if self._judge_selected_for_sampling(config, auth.institucion_id):
                                judge_service = self._judge_service_for(config, auth.institucion_id)
                                judge = judge_service.evaluate(
                                    question=query_text, answer=answer, chunks=retrieved.chunks
                                )
                                if judge.ok:
                                    score_fidelidad = judge.fidelidad
                                    score_relevancia = judge.relevancia
                                    score_contexto = judge.contexto
                                    observaciones = f"{observaciones} | JUDGE:ok ({judge.model})"
                                else:
                                    observaciones = f"{observaciones} | JUDGE_FAILED: {judge.error}"
                            else:
                                observaciones = f"{observaciones} | JUDGE:skipped_sample"
                    else:
                        answer = LLM_UNAVAILABLE_MESSAGE
                        modelo_ia = generation.model
                        observaciones = f"LLM_FAILED: {generation.error} [regenerate]"
                else:
                    preview = retrieved.chunks[0].chunk_text[:200]
                    answer = (
                        f"MOCK: Recuperé {retrieved.total} fragmentos relevantes. "
                        f"Primer fragmento: {preview} (respuesta real pendiente de OpenRouter)."
                    )
                    modelo_ia = "mock-retrieval"
                    observaciones = "RETRIEVAL: contexto recuperado; respuesta pendiente de OpenRouter [regenerate]"
                    tokens_input = len(query_text.split())
                    tokens_output = len(answer.split())
            else:
                answer = DOMAIN_GUARD_MESSAGE
                observaciones = "GUARD: sin contexto institucional recuperado [regenerate]"
                tokens_input = len(query_text.split())
                tokens_output = len(answer.split())
        else:
            answer = f"MOCK: Recibí tu consulta institucional: {user_msg.get('contenido_texto')}"
            observaciones = "MOCK: sin evaluación automática [regenerate]"
            tokens_input = len(query_text.split())
            tokens_output = len(answer.split())

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if pii_enabled and last_assistant.get("audit_id"):
            try:
                repo = getattr(self.pii_service, "repository", None)
                mappings = repo.list_by_audit(last_assistant["audit_id"]) if repo else []
            except Exception:  # noqa: BLE001
                mappings = []
            if mappings:
                restored = self.pii_service.restore(answer, mappings)
                if restored != answer:
                    answer = restored
                    observaciones = f"{observaciones} | DEANON:{len(mappings)} | PII:{len(mappings)}"

        assistant_msg = self.messages_repository.update_message(
            last_assistant["id"],
            contenido_texto=answer,
            proveedor_ia="OpenRouter",
            modelo_ia=modelo_ia,
            temperatura=0.2,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tiempo_respuesta_ms=elapsed_ms,
        ) or last_assistant

        audit_log = self.audit_repository.create_audit_log(
            conversation_id=conversation_id,
            message_id=last_assistant["id"],
            external_auth_id=auth.external_auth_id,
            pregunta_original=user_msg.get("contenido_texto"),
            pregunta_anonimizada=user_msg.get("contenido_anonimizado"),
            respuesta_texto=answer,
            proveedor_ia="OpenRouter",
            modelo_ia=modelo_ia,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tiempo_respuesta_ms=elapsed_ms,
            observaciones=observaciones,
            embedding_model=embedding_model,
            institucion_id=auth.institucion_id,
            score_fidelidad=score_fidelidad,
            score_relevancia=score_relevancia,
            score_contexto=score_contexto,
        )
        assistant_msg = (
            self.messages_repository.update_message_audit_id(last_assistant["id"], audit_log["id"])
            or assistant_msg
        )

        if sources:
            try:
                traceability_rows = [
                    {
                        "mensaje_id": last_assistant["id"],
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
            except Exception as exc:  # noqa: BLE001
                logger.warning("Message_documents persist failed conversation_id=%s error=%s", conversation_id, exc)

        self.conversations_repository.touch_conversation(conversation_id)
        return {
            "conversation_id": conversation_id,
            "response": answer,
            "sources": sources,
            "audit_id": audit_log["id"],
            "assistant_message": assistant_msg,
        }

    def _judge_selected_for_sampling(
        self,
        config: ConfigService,
        institucion_id: Optional[int],
    ) -> bool:
        """Decide si esta consulta se evalúa con el juez.

        `judge_sample_rate` permite mantener el juez fuera de la ruta crítica
        (RNF-05) y evaluar solo una fracción configurable de consultas.
        0.0 = ninguna; 1.0 = todas (corridas de evaluación).
        """
        rate = config.get_float(
            "judge_sample_rate", institucion_id, settings.judge_sample_rate
        )
        rate = min(1.0, max(0.0, rate))
        if rate <= 0.0:
            return False
        if rate >= 1.0:
            return True
        return random.random() < rate

    def _generation_service_for(
        self,
        config: ConfigService,
        institucion_id: Optional[int],
    ) -> GenerationService:
        """Resuelve el modelo de generación con precedencia institucional.

        Orden: institución > global (`config_parametros`) > `settings`/.env.
        Si el servicio fue inyectado (tests), se respeta sin cambios.
        """
        if self._generation_service_injected:
            return self.generation_service
        model = config.get_str("llm_model", institucion_id, settings.llm_model)
        if model == self.generation_service.model:
            return self.generation_service
        return GenerationService(
            model=model,
            temperature=self.generation_service.temperature,
            max_tokens=self.generation_service.max_tokens,
            system_prompt=self.generation_service.system_prompt,
        )

    def _judge_service_for(
        self,
        config: ConfigService,
        institucion_id: Optional[int],
    ) -> JudgeService:
        """Resuelve el modelo del juez con precedencia institucional."""
        if self._judge_service_injected:
            return self.judge_service
        model = config.get_str("judge_model", institucion_id, settings.judge_model)
        if model == self.judge_service.model:
            return self.judge_service
        return JudgeService(
            model=model,
            temperature=self.judge_service.temperature,
            max_tokens=self.judge_service.max_tokens,
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
            content = row.get("contenido_anonimizado") or row.get("contenido_texto")
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
        conversation = self.get_owned_conversation(conversation_id, auth.external_auth_id, auth.institucion_id)
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
            institucion_id=auth.institucion_id,
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
        # Validación de institución: el mensaje debe pertenecer a la misma institución
        conversation = self.conversations_repository.get_conversation(
            message.get("conversacion_id"), institucion_id=auth.institucion_id
        )
        if not conversation:
            return None  # 404: mensaje de otra institución
        return self.feedback_repository.create_feedback(
            message_id=message_id,
            rating=rating,
            comment=comment,
            audit_id=audit_id,
            external_auth_id=auth.external_auth_id,
            institucion_id=auth.institucion_id,
        )
