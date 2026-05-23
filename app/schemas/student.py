from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import AudioInteractionOut, ConversationOut, MessageOut


class StudentQueryIn(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: Optional[int] = None


class RagDocumentRef(BaseModel):
    documento_version_id: int
    score_similitud: float
    chunk_referencia: int


class StudentQueryOut(BaseModel):
    conversation: ConversationOut
    user_message: MessageOut
    assistant_message: MessageOut
    answer: str
    rag_documents: List[RagDocumentRef] = []


class StudentVoiceQueryOut(BaseModel):
    conversation: ConversationOut
    user_message: MessageOut
    assistant_message: MessageOut
    audio_interaction: AudioInteractionOut
    transcription: str
    answer: str
    rag_documents: List[RagDocumentRef] = []


class StudentHistoryOut(BaseModel):
    conversations: List[ConversationOut]
