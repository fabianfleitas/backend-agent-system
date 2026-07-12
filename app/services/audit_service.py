from __future__ import annotations

from typing import Optional

from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, audit_repository: Optional[AuditRepository] = None) -> None:
        self.audit_repository = audit_repository or AuditRepository()

    def list_audit_logs(self) -> list[dict]:
        return self.audit_repository.list_audit_logs()

