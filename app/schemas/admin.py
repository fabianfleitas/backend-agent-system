from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import DocumentOut, DocumentVersionOut


class AdminUploadDocumentOut(BaseModel):
    document: DocumentOut
    version: DocumentVersionOut


class AdminUploadVersionOut(BaseModel):
    document: DocumentOut
    version: DocumentVersionOut


class DocumentDetailOut(BaseModel):
    id: int
    categoria_id: Optional[int] = None
    codigo_documento: Optional[str] = None
    titulo: str
    descripcion: Optional[str] = None
    activo: bool = True
    fecha_creacion: str
    versiones: List[DocumentVersionOut] = []


class AdminReindexIn(BaseModel):
    documento_id: Optional[int] = Field(default=None)


class AdminReindexOut(BaseModel):
    updated_versions: int
