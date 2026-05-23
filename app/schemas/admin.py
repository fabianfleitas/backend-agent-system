from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import AuditLogOut, DocumentOut, DocumentVersionOut


class AdminUploadDocumentOut(BaseModel):
    document: DocumentOut
    version: DocumentVersionOut


class AdminListDocumentsOut(BaseModel):
    documents: List[DocumentOut]


class AdminReindexIn(BaseModel):
    documento_id: Optional[int] = Field(default=None)


class AdminReindexOut(BaseModel):
    updated_versions: int


class AdminAuditOut(BaseModel):
    logs: List[AuditLogOut]
