from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import AuthContext, get_auth_context
from app.schemas.common import (
    ConversationDetailOut,
    ConversationSummaryOut,
    MessageOut,
    PaginatedResponse,
    PaginationMeta,
)
from app.services.mock_store import store

router = APIRouter()


def _summary_out(c) -> ConversationSummaryOut:
    return ConversationSummaryOut(
        id=c.id,
        title=c.titulo,
        last_interaction=c.ultima_interaccion,
        message_count=store.get_message_count(c.id),
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
        audit_id=m.audit_id,
    )


def _check_ownership(conversation_id: int, external_auth_id: str):
    conv = store.get_conversation(conversation_id)
    if not conv or conv.usuario_external_auth_id != external_auth_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


@router.get("/", response_model=PaginatedResponse[ConversationSummaryOut])
def list_conversations(
    include_hidden: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_auth_context),
) -> PaginatedResponse[ConversationSummaryOut]:
    conversations = store.list_conversations(auth.external_auth_id, include_hidden=include_hidden)
    total = len(conversations)
    page = conversations[offset : offset + limit]
    return PaginatedResponse[ConversationSummaryOut](
        items=[_summary_out(c) for c in page],
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post("/", response_model=ConversationDetailOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    auth: AuthContext = Depends(get_auth_context),
) -> ConversationDetailOut:
    title = f"Conversación {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
    conv = store.create_conversation(auth.external_auth_id, titulo=title)
    return ConversationDetailOut(id=conv.id, title=conv.titulo, messages=[])


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: int,
    auth: AuthContext = Depends(get_auth_context),
) -> ConversationDetailOut:
    conv = _check_ownership(conversation_id, auth.external_auth_id)
    messages = store.get_conversation_messages(conversation_id)
    return ConversationDetailOut(
        id=conv.id,
        title=conv.titulo,
        messages=[_message_out(m) for m in messages],
    )


@router.delete("/{conversation_id}", response_model=ConversationSummaryOut)
def hide_conversation(
    conversation_id: int,
    auth: AuthContext = Depends(get_auth_context),
) -> ConversationSummaryOut:
    try:
        conv = store.hide_conversation(auth.external_auth_id, conversation_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return _summary_out(conv)


@router.get("/{conversation_id}/messages", response_model=List[MessageOut])
def get_conversation_messages(
    conversation_id: int,
    auth: AuthContext = Depends(get_auth_context),
) -> List[MessageOut]:
    _check_ownership(conversation_id, auth.external_auth_id)
    messages = store.get_conversation_messages(conversation_id)
    return [_message_out(m) for m in messages]
