from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.security import AuthContext, get_auth_context
from app.repositories.audit_repository import AuditRepository
from app.schemas.chat import ChatQueryIn, ChatQueryOut, ChatVoiceOut
from app.schemas.common import AudioInteractionOut, ChatFeedbackIn, ChatFeedbackOut, MessageOut, SourceOut
from app.services.audio_service import AudioService
from app.services.chat_service import ChatService
from app.services.synthesis_service import SynthesisService
from app.services.transcription_service import TranscriptionService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_chat_service() -> ChatService:
    return ChatService()


def _get_audio_service() -> AudioService:
    return AudioService()


def _get_transcription_service() -> TranscriptionService:
    return TranscriptionService()


def _get_synthesis_service() -> SynthesisService:
    return SynthesisService()


def _get_audit_repository() -> AuditRepository:
    return AuditRepository()


def _audio_out(a) -> AudioInteractionOut:
    if isinstance(a, dict):
        return AudioInteractionOut(
            id=a["id"],
            mensaje_id=a["mensaje_id"],
            ruta_audio_original=a["ruta_audio_original"],
            ruta_audio_respuesta=a.get("ruta_audio_respuesta"),
            transcripcion=a.get("transcripcion"),
            transcription_model=a.get("transcription_model"),
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
        transcription_model=a.transcription_model,
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

    return ChatQueryOut(
        response=result.response,
        sources=[SourceOut(**s) for s in result.sources],
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
    chat_service: ChatService = Depends(_get_chat_service),
    audio_service: AudioService = Depends(_get_audio_service),
    transcription_service: TranscriptionService = Depends(_get_transcription_service),
    synthesis_service: SynthesisService = Depends(_get_synthesis_service),
    audit_repository: AuditRepository = Depends(_get_audit_repository),
) -> ChatVoiceOut:
    audio_bytes = await audio.read()

    transcription: str
    transcription_model = None
    duration = None
    if settings.stt_enabled:
        stt = transcription_service.transcribe(audio_bytes, audio.filename or "audio", audio.content_type)
        if not stt.ok:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No fue posible transcribir el audio. Intenta nuevamente.",
            )
        transcription = stt.text
        transcription_model = stt.model
        duration = stt.duration
    else:
        transcription = "MOCK: transcripción simulada del audio"

    result = await run_in_threadpool(
        chat_service.answer_voice_query,
        auth=auth,
        conversation_id=conversation_id,
        transcription=transcription,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    response_audio_bytes = b""
    response_content_type = "audio/wav"
    if settings.tts_enabled:
        synth = await run_in_threadpool(synthesis_service.synthesize, result.response)
        if synth.ok:
            response_audio_bytes = synth.audio_bytes
            response_content_type = synth.content_type
        else:
            logger.warning(
                "TTS failed conversation_id=%s model=%s error=%s",
                conversation_id,
                synth.model,
                synth.error,
            )
            current = result.audit_log.get("observaciones") or ""
            audit_repository.update_observaciones(
                result.audit_log["id"],
                f"{current} | TTS_FAILED: {synth.error}",
            )

    audio_interaction = audio_service.create_audio_interaction(
        auth=auth,
        conversation_id=conversation_id,
        message_id=result.assistant_message["id"],
        audio_bytes=audio_bytes,
        source_filename=audio.filename,
        source_content_type=audio.content_type,
        transcription=transcription,
        transcription_model=transcription_model,
        duracion_segundos=duration,
        response_audio_bytes=response_audio_bytes,
        response_content_type=response_content_type,
    )

    return ChatVoiceOut(
        response=result.response,
        sources=[SourceOut(**s) for s in result.sources],
        transcription=transcription,
        audio_interaction=_audio_out(audio_interaction),
        audit_id=uuid.UUID(result.audit_log["id"]),
        conversation_id=result.conversation_id,
        user_message=_message_out(result.user_message),
        assistant_message=_message_out(result.assistant_message),
    )


@router.get("/audio/{audio_interaction_id}")
def get_audio_response(
    audio_interaction_id: int,
    auth: AuthContext = Depends(get_auth_context),
    audio_service: AudioService = Depends(_get_audio_service),
) -> Response:
    try:
        audio_data = audio_service.get_response_audio(
            audio_interaction_id=audio_interaction_id,
            auth=auth,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para acceder a este audio",
        )

    if not audio_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio no encontrado",
        )

    audio_bytes, content_type = audio_data
    return Response(
        content=audio_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "private, max-age=3600",
        },
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
