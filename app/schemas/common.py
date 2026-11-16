from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Generic, List, Optional, Sequence, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class UserRole(str, Enum):
    STUDENT = "STUDENT"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


class DocumentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class ApiError(BaseModel):
    detail: str


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int


class PaginatedResponse(BaseModel, Generic[T]):
    items: Sequence[T]
    pagination: PaginationMeta


class ConversationSummaryOut(BaseModel):
    id: int
    title: str
    last_interaction: datetime
    message_count: int


class AdminConversationOut(BaseModel):
    id: int
    title: str
    last_interaction: datetime
    message_count: int
    external_auth_id: str


class ConversationDetailOut(BaseModel):
    id: int
    title: str
    messages: List[MessageOut]


class MessageOut(BaseModel):
    id: int
    conversacion_id: int
    rol_mensaje: str
    contenido_texto: str
    proveedor_ia: Optional[str] = None
    modelo_ia: Optional[str] = None
    temperatura: Optional[float] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    tiempo_respuesta_ms: Optional[float] = None
    fecha_envio: datetime
    audit_id: Optional[UUID] = None
    sources: List[SourceOut] = []
    rating: Optional[int] = None
    feedback_comment: Optional[str] = None


class AudioInteractionOut(BaseModel):
    id: int
    mensaje_id: int
    ruta_audio_original: str
    ruta_audio_respuesta: Optional[str] = None
    transcripcion: Optional[str] = None
    transcription_model: Optional[str] = None
    duracion_segundos: Optional[float] = None
    formato_audio: Optional[str] = None
    tamano_bytes: Optional[int] = None
    fecha_creacion: datetime


class SourceOut(BaseModel):
    document_id: int
    document: str
    page: int
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ChatFeedbackIn(BaseModel):
    message_id: int
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None
    audit_id: UUID


class ChatFeedbackOut(BaseModel):
    id: int
    message_id: int
    rating: int
    comment: Optional[str] = None
    audit_id: UUID
    created_at: datetime


class UserOut(BaseModel):
    external_auth_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: UserRole
    institucion_id: Optional[int] = None
    tipo_miembro: Optional[str] = None
    is_platform_admin: bool = False
    nombre_institucion: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class UserUpdateIn(BaseModel):
    full_name: Optional[str] = None


class DocumentVersionOut(BaseModel):
    id: int
    documento_id: int
    numero_version: int
    ruta_archivo: str
    status: DocumentStatus = DocumentStatus.PENDING
    es_version_activa: bool = True
    total_chunks: int = 0
    embedding_model: Optional[str] = None
    fecha_carga: datetime
    indexed_at: Optional[datetime] = None
    cargado_por_external_auth_id: str


class DocumentOut(BaseModel):
    id: int
    categoria_id: Optional[int] = None
    codigo_documento: Optional[str] = None
    titulo: str
    descripcion: Optional[str] = None
    activo: bool = True
    fecha_creacion: datetime
    version_activa: Optional[DocumentVersionOut] = None


class AuditLogOut(BaseModel):
    id: UUID
    mensaje_id: Optional[int] = None
    score_fidelidad: Optional[float] = None
    score_relevancia: Optional[float] = None
    score_contexto: Optional[float] = None
    observaciones: Optional[str] = None
    fecha_evaluacion: datetime
