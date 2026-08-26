from __future__ import annotations

from typing import Optional

from app.core.security import AuthContext
from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, audit_repository: Optional[AuditRepository] = None) -> None:
        self.audit_repository = audit_repository or AuditRepository()

    def list_audit_logs(self, auth=None) -> list[dict]:
        institution_id = None
        if auth is not None and not auth.is_platform_admin:
            institution_id = auth.institucion_id
        return self.audit_repository.list_audit_logs(institucion_id=institution_id)

