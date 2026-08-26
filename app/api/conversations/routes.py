from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import AuthContext, get_auth_context
from app.schemas.common import (
    ConversationDetailOut,
    ConversationSummaryOut,
    MessageOut,
    PaginatedResponse,
    PaginationMeta,
)
from app.services.conversations_service import ConversationsService

router = APIRouter()


def _get_service() -> ConversationsService:
    return ConversationsService()


def _summary_out(c: dict, message_count: int) -> ConversationSummaryOut:
    return ConversationSummaryOut(
        id=c["id"],
        title=c["title"],
        last_interaction=c["last_interaction"] or c["fecha_creacion"],
        message_count=message_count,
    )


def _message_out(m: dict) -> MessageOut:
    return MessageOut(
        id=m["id"],
        conversacion_id=m["conversacion_id"],
        rol_mensaje=m["rol_mensaje"],
        contenido_texto=m["contenido_texto"],
        proveedor_ia=m.get("proveedor_ia"),
        modelo_ia=m.get("modelo_ia"),
        temperatura=float(m["temperatura"]) if m.get("temperatura") is not None else None,
        tokens_input=m.get("tokens_input"),
        tokens_output=m.get("tokens_output"),
        tiempo_respuesta_ms=m.get("tiempo_respuesta_ms"),
        fecha_envio=m["fecha_envio"],
        audit_id=UUID(m["audit_id"]) if m.get("audit_id") else None,
    )


def _check_ownership(
    service: ConversationsService,
    conversation_id: int,
    auth: AuthContext,
) -> dict:
    conv = service.get_owned_conversation(conversation_id, auth.external_auth_id, auth.institucion_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


@router.get("/", response_model=PaginatedResponse[ConversationSummaryOut])
def list_conversations(
    include_hidden: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_auth_context),
) -> PaginatedResponse[ConversationSummaryOut]:
    service = _get_service()
    conversations = service.list_conversations(auth.external_auth_id, include_hidden=include_hidden, institucion_id=auth.institucion_id)
    total = len(conversations)
    page = conversations[offset : offset + limit]
    return PaginatedResponse[ConversationSummaryOut](
        items=[_summary_out(c, service.count_messages(c["id"])) for c in page],
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post("/", response_model=ConversationDetailOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    auth: AuthContext = Depends(get_auth_context),
) -> ConversationDetailOut:
    conv = _get_service().create_conversation(auth)
    return ConversationDetailOut(id=conv["id"], title=conv["title"], messages=[])


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: int,
    auth: AuthContext = Depends(get_auth_context),
) -> ConversationDetailOut:
    service = _get_service()
    conv = _check_ownership(service, conversation_id, auth)
    messages = service.get_messages(conversation_id)
    return ConversationDetailOut(
        id=conv["id"],
        title=conv["title"],
        messages=[_message_out(m) for m in messages],
    )


@router.delete("/{conversation_id}", response_model=ConversationSummaryOut)
def hide_conversation(
    conversation_id: int,
    auth: AuthContext = Depends(get_auth_context),
) -> ConversationSummaryOut:
    service = _get_service()
    conv = service.hide_conversation(auth.external_auth_id, conversation_id, auth.institucion_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return _summary_out(conv, service.count_messages(conv["id"]))


@router.get("/{conversation_id}/messages", response_model=List[MessageOut])
def get_conversation_messages(
    conversation_id: int,
    auth: AuthContext = Depends(get_auth_context),
) -> List[MessageOut]:
    service = _get_service()
    _check_ownership(service, conversation_id, auth)
    messages = service.get_messages(conversation_id)
    return [_message_out(m) for m in messages]
