from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import DocumentOut, DocumentVersionOut


class AdminUploadDocumentOut(BaseModel):
    document: DocumentOut
    version: DocumentVersionOut


class AdminReindexIn(BaseModel):
    documento_id: Optional[int] = Field(default=None)


class AdminReindexOut(BaseModel):
    updated_versions: int
