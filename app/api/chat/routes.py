from __future__ import annotations

import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.core.config import settings
from app.core.security import AuthContext, get_auth_context
from app.schemas.chat import ChatQueryIn, ChatQueryOut, ChatVoiceOut
from app.schemas.common import (
    AudioInteractionOut,
    ChatFeedbackIn,
    ChatFeedbackOut,
    MessageOut,
    SourceOut,
)
from app.services.mock_store import store
from app.utils.files import ensure_dir, safe_join, write_bytes

router = APIRouter()


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
        audit_id=uuid.UUID(m.audit_id) if m.audit_id else None,
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


@router.post("/query", response_model=ChatQueryOut)
def chat_query(
    payload: ChatQueryIn,
    auth: AuthContext = Depends(get_auth_context),
) -> ChatQueryOut:
    conv = store.get_conversation(payload.conversation_id)
    if not conv or conv.usuario_external_auth_id != auth.external_auth_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    store.add_message(
        conversation_id=conv.id,
        role="USER",
        content=payload.message,
    )

    start = time.perf_counter()
    answer = f"MOCK: Recibí tu consulta institucional: {payload.message}"
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assistant_msg = store.add_message(
        conversation_id=conv.id,
        role="ASSISTANT",
        content=answer,
        proveedor_ia="OpenRouter",
        modelo_ia="mock",
        temperatura=0.2,
        tokens_input=len(payload.message.split()),
        tokens_output=len(answer.split()),
        tiempo_respuesta_ms=elapsed_ms,
    )

    audit_log = store.add_audit_log(
        mensaje_id=assistant_msg.id,
        observaciones="MOCK: sin evaluación automática",
    )
    assistant_msg.audit_id = audit_log.id

    sources = [
        SourceOut(
            document_id=1,
            document="Reglamento Académico.pdf",
            page=12,
            similarity_score=0.92,
        ),
    ]

    return ChatQueryOut(
        response=answer,
        sources=sources,
        audit_id=uuid.UUID(audit_log.id),
    )


@router.post("/voice", response_model=ChatVoiceOut)
async def chat_voice(
    audio: UploadFile = File(...),
    conversation_id: int = Query(...),
    auth: AuthContext = Depends(get_auth_context),
) -> ChatVoiceOut:
    conv = store.get_conversation(conversation_id)
    if not conv or conv.usuario_external_auth_id != auth.external_auth_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    audio_bytes = await audio.read()
    ensure_dir(settings.storage_audio_dir)
    ext = os.path.splitext(audio.filename or "")[1] or ".bin"
    filename = f"{uuid.uuid4().hex}{ext}"
    audio_path = safe_join(settings.storage_audio_dir, filename)
    write_bytes(audio_path, audio_bytes)

    transcription = "MOCK: transcripción simulada del audio"

    store.add_message(
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
        mensaje_id=assistant_msg.id,
        ruta_audio_original=audio_path,
        ruta_audio_respuesta=response_audio_path,
        transcripcion=transcription,
        formato_audio=audio.content_type,
        tamano_bytes=len(audio_bytes),
        duracion_segundos=None,
    )

    audit_log = store.add_audit_log(
        mensaje_id=assistant_msg.id,
        observaciones="MOCK: sin evaluación automática",
    )
    assistant_msg.audit_id = audit_log.id

    sources = [
        SourceOut(
            document_id=1,
            document="Reglamento Académico.pdf",
            page=12,
            similarity_score=0.92,
        ),
    ]

    return ChatVoiceOut(
        response=answer,
        sources=sources,
        transcription=transcription,
        audio_interaction=_audio_out(audio_interaction),
        audit_id=uuid.UUID(audit_log.id),
    )


@router.post("/feedback", response_model=ChatFeedbackOut)
def chat_feedback(
    payload: ChatFeedbackIn,
    auth: AuthContext = Depends(get_auth_context),
) -> ChatFeedbackOut:
    fb = store.add_feedback(
        message_id=payload.message_id,
        rating=payload.rating,
        comment=payload.comment,
        audit_id=str(payload.audit_id),
    )

    return ChatFeedbackOut(
        id=fb.id,
        message_id=fb.message_id,
        rating=fb.rating,
        comment=fb.comment,
        audit_id=uuid.UUID(fb.audit_id),
        created_at=fb.created_at,
    )
