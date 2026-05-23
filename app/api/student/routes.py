from __future__ import annotations

import os
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.core.config import settings
from app.core.security import AuthContext, get_auth_context
from app.schemas.common import AudioInteractionOut, ConversationOut, MessageOut
from app.schemas.student import StudentHistoryOut, StudentQueryIn, StudentQueryOut, StudentVoiceQueryOut
from app.services.mock_store import store
from app.utils.files import ensure_dir, safe_join, write_bytes


router = APIRouter()


def _conversation_out(c) -> ConversationOut:
    return ConversationOut(
        id=c.id,
        usuario_external_auth_id=c.usuario_external_auth_id,
        titulo=c.titulo,
        oculto_usuario=c.oculto_usuario,
        estado=c.estado,
        fecha_inicio=c.fecha_inicio,
        ultima_interaccion=c.ultima_interaccion,
    )


def _message_out(m) -> MessageOut:
    return MessageOut(
        id=m.id,
        conversacion_id=m.conversacion_id,
        rol_mensaje=m.rol_mensaje,
        contenido_texto=m.contenido_texto,
        proveedor_ia=m.proveedor_ia,
        modelo_ia=m.modelo_ia,
        temperatura=m.temperatura,
        tokens_input=m.tokens_input,
        tokens_output=m.tokens_output,
        tiempo_respuesta_ms=m.tiempo_respuesta_ms,
        fecha_envio=m.fecha_envio,
    )


def _audio_out(a) -> AudioInteractionOut:
    return AudioInteractionOut(
        id=a.id,
        mensaje_id=a.mensaje_id,
        ruta_audio_original=a.ruta_audio_original,
        ruta_audio_respuesta=a.ruta_audio_respuesta,
        transcripcion=a.transcripcion,
        duracion_segundos=a.duracion_segundos,
        formato_audio=a.formato_audio,
        tamano_bytes=a.tamano_bytes,
        fecha_creacion=a.fecha_creacion,
    )


def _get_or_create_conversation(auth: AuthContext, conversation_id: Optional[int]) -> object:
    if conversation_id is None:
        titulo = f"Conversación {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
        return store.create_conversation(auth.external_auth_id, titulo=titulo)

    conv = store.get_conversation(conversation_id)
    if not conv or conv.usuario_external_auth_id != auth.external_auth_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


@router.post("/query", response_model=StudentQueryOut)
def student_query(payload: StudentQueryIn, auth: AuthContext = Depends(get_auth_context)) -> StudentQueryOut:
    conv = _get_or_create_conversation(auth, payload.conversation_id)

    user_msg = store.add_message(
        conversation_id=conv.id,
        role="USER",
        content=payload.question,
    )

    start = time.perf_counter()
    answer = f"MOCK: Recibí tu consulta institucional: {payload.question}"
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assistant_msg = store.add_message(
        conversation_id=conv.id,
        role="ASSISTANT",
        content=answer,
        proveedor_ia="OpenRouter",
        modelo_ia="mock",
        temperatura=0.2,
        tokens_input=len(payload.question.split()),
        tokens_output=len(answer.split()),
        tiempo_respuesta_ms=elapsed_ms,
    )

    store.add_audit_log(mensaje_id=assistant_msg.id, observaciones="MOCK: sin evaluación automática")

    return StudentQueryOut(
        conversation=_conversation_out(conv),
        user_message=_message_out(user_msg),
        assistant_message=_message_out(assistant_msg),
        answer=answer,
        rag_documents=[],
    )


@router.post("/voice-query", response_model=StudentVoiceQueryOut)
async def student_voice_query(
    audio: UploadFile = File(...),
    conversation_id: Optional[int] = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
) -> StudentVoiceQueryOut:
    conv = _get_or_create_conversation(auth, conversation_id)

    audio_bytes = await audio.read()
    ensure_dir(settings.storage_audio_dir)
    ext = os.path.splitext(audio.filename or "")[1] or ".bin"
    filename = f"{uuid.uuid4().hex}{ext}"
    audio_path = safe_join(settings.storage_audio_dir, filename)
    write_bytes(audio_path, audio_bytes)

    transcription = "MOCK: transcripción simulada del audio"

    user_msg = store.add_message(
        conversation_id=conv.id,
        role="USER",
        content=transcription,
    )

    start = time.perf_counter()
    answer = "MOCK: respuesta simulada basada en reglamentos institucionales (RAG aún no implementado)"
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assistant_msg = store.add_message(
        conversation_id=conv.id,
        role="ASSISTANT",
        content=answer,
        proveedor_ia="OpenRouter",
        modelo_ia="mock",
        temperatura=0.2,
        tokens_input=len(transcription.split()),
        tokens_output=len(answer.split()),
        tiempo_respuesta_ms=elapsed_ms,
    )

    ensure_dir(settings.storage_audio_dir)
    response_audio_filename = f"{uuid.uuid4().hex}.wav"
    response_audio_path = safe_join(settings.storage_audio_dir, response_audio_filename)
    write_bytes(response_audio_path, b"")

    audio_interaction = store.add_audio_interaction(
        mensaje_id=user_msg.id,
        ruta_audio_original=audio_path,
        ruta_audio_respuesta=response_audio_path,
        transcripcion=transcription,
        formato_audio=audio.content_type,
        tamano_bytes=len(audio_bytes),
        duracion_segundos=None,
    )

    store.add_audit_log(mensaje_id=assistant_msg.id, observaciones="MOCK: sin evaluación automática")

    return StudentVoiceQueryOut(
        conversation=_conversation_out(conv),
        user_message=_message_out(user_msg),
        assistant_message=_message_out(assistant_msg),
        audio_interaction=_audio_out(audio_interaction),
        transcription=transcription,
        answer=answer,
        rag_documents=[],
    )


@router.get("/history", response_model=StudentHistoryOut)
def student_history(
    include_hidden: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context),
) -> StudentHistoryOut:
    conversations = store.list_conversations(auth.external_auth_id, include_hidden=include_hidden)
    return StudentHistoryOut(conversations=[_conversation_out(c) for c in conversations])


@router.patch("/history/{conversation_id}/hide", response_model=ConversationOut)
def hide_conversation(conversation_id: int, auth: AuthContext = Depends(get_auth_context)) -> ConversationOut:
    try:
        conv = store.hide_conversation(auth.external_auth_id, conversation_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return _conversation_out(conv)
