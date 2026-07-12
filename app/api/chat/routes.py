from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.core.security import AuthContext, get_auth_context
from app.schemas.chat import ChatQueryIn, ChatQueryOut, ChatVoiceOut
from app.schemas.common import AudioInteractionOut, ChatFeedbackIn, ChatFeedbackOut, MessageOut, SourceOut
from app.services.audio_service import AudioService
from app.services.chat_service import ChatService

router = APIRouter()


def _get_chat_service() -> ChatService:
    return ChatService()


def _audio_out(a) -> AudioInteractionOut:
    if isinstance(a, dict):
        return AudioInteractionOut(
            id=a["id"],
            mensaje_id=a["mensaje_id"],
            ruta_audio_original=a["ruta_audio_original"],
            ruta_audio_respuesta=a.get("ruta_audio_respuesta"),
            transcripcion=a.get("transcripcion"),
            duracion_segundos=float(a["duracion_segundos"]) if a.get("duracion_segundos") is not None else None,
            formato_audio=a.get("formato_audio"),
            tamano_bytes=a.get("tamano_bytes"),
            fecha_creacion=a["fecha_creacion"],
        )
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


def _message_out(message: dict) -> MessageOut:
    return MessageOut(
        id=message["id"],
        conversacion_id=message["conversacion_id"],
        rol_mensaje=message["rol_mensaje"],
        contenido_texto=message["contenido_texto"],
        proveedor_ia=message.get("proveedor_ia"),
        modelo_ia=message.get("modelo_ia"),
        temperatura=float(message["temperatura"]) if message.get("temperatura") is not None else None,
        tokens_input=message.get("tokens_input"),
        tokens_output=message.get("tokens_output"),
        tiempo_respuesta_ms=message.get("tiempo_respuesta_ms"),
        fecha_envio=message["fecha_envio"],
        audit_id=uuid.UUID(message["audit_id"]) if message.get("audit_id") else None,
    )


@router.post("/query", response_model=ChatQueryOut)
def chat_query(
    payload: ChatQueryIn,
    auth: AuthContext = Depends(get_auth_context),
) -> ChatQueryOut:
    result = _get_chat_service().answer_text_query(
        auth=auth,
        conversation_id=payload.conversation_id,
        message=payload.message,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    sources = [
        SourceOut(
            document_id=1,
            document="Reglamento Académico.pdf",
            page=12,
            similarity_score=0.92,
        ),
    ]

    return ChatQueryOut(
        response=result.response,
        sources=sources,
        audit_id=uuid.UUID(result.audit_log["id"]),
        conversation_id=result.conversation_id,
        user_message=_message_out(result.user_message),
        assistant_message=_message_out(result.assistant_message),
    )


@router.post("/voice", response_model=ChatVoiceOut)
async def chat_voice(
    audio: UploadFile = File(...),
    conversation_id: int = Query(...),
    auth: AuthContext = Depends(get_auth_context),
) -> ChatVoiceOut:
    audio_bytes = await audio.read()
    transcription = "MOCK: transcripción simulada del audio"
    result = _get_chat_service().answer_voice_query(
        auth=auth,
        conversation_id=conversation_id,
        transcription=transcription,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    audio_interaction = AudioService().create_audio_interaction(
        auth=auth,
        conversation_id=conversation_id,
        message_id=result.assistant_message["id"],
        audio_bytes=audio_bytes,
        source_filename=audio.filename,
        source_content_type=audio.content_type,
        transcription=transcription,
    )

    sources = [
        SourceOut(
            document_id=1,
            document="Reglamento Académico.pdf",
            page=12,
            similarity_score=0.92,
        ),
    ]

    return ChatVoiceOut(
        response=result.response,
        sources=sources,
        transcription=transcription,
        audio_interaction=_audio_out(audio_interaction),
        audit_id=uuid.UUID(result.audit_log["id"]),
        conversation_id=result.conversation_id,
        user_message=_message_out(result.user_message),
        assistant_message=_message_out(result.assistant_message),
    )


@router.post("/feedback", response_model=ChatFeedbackOut)
def chat_feedback(
    payload: ChatFeedbackIn,
    auth: AuthContext = Depends(get_auth_context),
) -> ChatFeedbackOut:
    fb = _get_chat_service().create_feedback(
        auth=auth,
        message_id=payload.message_id,
        rating=payload.rating,
        comment=payload.comment,
        audit_id=str(payload.audit_id),
    )
    if not fb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    return ChatFeedbackOut(
        id=fb["id"],
        message_id=fb["message_id"],
        rating=fb["rating"],
        comment=fb.get("comment"),
        audit_id=uuid.UUID(fb["audit_id"]),
        created_at=fb["created_at"],
    )
