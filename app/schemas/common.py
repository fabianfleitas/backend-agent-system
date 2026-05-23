from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ApiError(BaseModel):
    detail: str


class ConversationOut(BaseModel):
    id: int
    usuario_external_auth_id: str
    titulo: str
    oculto_usuario: bool
    estado: str
    fecha_inicio: datetime
    ultima_interaccion: datetime


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


class AudioInteractionOut(BaseModel):
    id: int
    mensaje_id: int
    ruta_audio_original: str
    ruta_audio_respuesta: Optional[str] = None
    transcripcion: Optional[str] = None
    duracion_segundos: Optional[float] = None
    formato_audio: Optional[str] = None
    tamano_bytes: Optional[int] = None
    fecha_creacion: datetime


class DocumentVersionOut(BaseModel):
    id: int
    documento_id: int
    numero_version: int
    ruta_archivo: str
    estado_indexacion: str
    es_version_activa: bool
    total_chunks: int = 0
    fecha_carga: datetime
    fecha_indexacion: Optional[datetime] = None
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
    id: int
    mensaje_id: int
    score_fidelidad: Optional[float] = None
    score_relevancia: Optional[float] = None
    score_contexto: Optional[float] = None
    observaciones: Optional[str] = None
    fecha_evaluacion: datetime
