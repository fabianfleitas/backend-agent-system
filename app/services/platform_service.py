from __future__ import annotations

from typing import Optional

from app.core.security import AuthContext
from app.repositories.institutions_repository import InstitutionsRepository
from app.repositories.audit_repository import AuditRepository
from app.services.admin_service import AdminService


class PlatformService:
    def __init__(
        self,
        institutions_repo: Optional[InstitutionsRepository] = None,
        audit_repo: Optional[AuditRepository] = None,
        admin_service: Optional[AdminService] = None,
    ) -> None:
        self.institutions_repo = institutions_repo or InstitutionsRepository()
        self.audit_repo = audit_repo or AuditRepository()
        self.admin_service = admin_service or AdminService()

    def list_institutions(self, activo: bool = True) -> list[dict]:
        return self.institutions_repo.list_instituciones(activo=activo)

    def get_institution(self, institucion_id: int) -> Optional[dict]:
        return self.institutions_repo.get_institucion(institucion_id)

    def list_members(self, institucion_id: int) -> list[dict]:
        return self.institutions_repo.list_members(institucion_id)

    def add_member(self, institucion_id: int, external_auth_id: str, tipo_miembro: str) -> dict:
        return self.institutions_repo.add_member(institucion_id, external_auth_id, tipo_miembro)

    def deactivate_member(self, membre_id: int) -> dict:
        return self.institutions_repo.deactivate_member(membre_id)

    def list_users(self, auth: Optional[AuthContext] = None) -> list:
        return self.admin_service.list_users(auth)

    def get_metrics(self, auth: Optional[AuthContext] = None, **filters) -> object:
        return self.admin_service.get_metrics(auth, **filters)

    def list_audit_logs(self, auth: Optional[AuthContext] = None, desde: Optional[str] = None, hasta: Optional[str] = None, modelo: Optional[str] = None) -> list[dict]:
        logs = self.audit_repo.list_audit_logs(institucion_id=None)
        if desde or hasta:
            logs = [l for l in logs if (l.get("fecha_evaluacion") or "")[:10] >= (desde or "") and (l.get("fecha_evaluacion") or "")[:10] <= (hasta or "9999-12-31")]
        if modelo:
            logs = [l for l in logs if modelo in (l.get("modelo_ia") or "")]
        return logs
