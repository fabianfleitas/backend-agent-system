from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import AudioInteractionOut, MessageOut, SourceOut


class ChatQueryIn(BaseModel):
    conversation_id: int
    message: str = Field(min_length=1)


class ChatRegenerateIn(BaseModel):
    conversation_id: int


class ChatRegenerateOut(BaseModel):
    response: str
    sources: List[SourceOut] = []
    audit_id: UUID
    conversation_id: int
    assistant_message: MessageOut


class ChatQueryOut(BaseModel):
    response: str
    sources: List[SourceOut] = []
    audit_id: UUID
    conversation_id: int
    user_message: MessageOut
    assistant_message: MessageOut


class ChatVoiceOut(BaseModel):
    response: str
    sources: List[SourceOut] = []
    transcription: str
    audio_interaction: AudioInteractionOut
    audit_id: UUID
    conversation_id: int
    user_message: MessageOut
    assistant_message: MessageOut
