from __future__ import annotations

from typing import Optional

from app.core.security import AuthContext
from app.repositories.institutions_repository import InstitutionsRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.billing_repository import BillingRepository
from app.repositories.users_repository import UsersRepository
from app.services.admin_service import AdminService
from app.schemas.common import UserOut
from app.services.admin_service import _parse_datetime, _role_out


class PlatformService:
    def __init__(
        self,
        institutions_repo: Optional[InstitutionsRepository] = None,
        audit_repo: Optional[AuditRepository] = None,
        admin_service: Optional[AdminService] = None,
        billing_repo: Optional[BillingRepository] = None,
        users_repository: Optional[UsersRepository] = None,
    ) -> None:
        self.institutions_repo = institutions_repo or InstitutionsRepository()
        self.audit_repo = audit_repo or AuditRepository()
        self.admin_service = admin_service or AdminService()
        self.billing_repo = billing_repo or BillingRepository()
        self.users_repository = users_repository or UsersRepository()

    def list_institutions(self, activo: bool = True) -> list[dict]:
        return self.institutions_repo.list_instituciones(activo=activo)

    def get_institution(self, institucion_id: int) -> Optional[dict]:
        return self.institutions_repo.get_institucion(institucion_id)

    def create_institution(self, **campos) -> dict:
        return self.institutions_repo.create_institucion(**campos)

    def update_institution(self, institucion_id: int, **campos) -> Optional[dict]:
        return self.institutions_repo.update_institucion(institucion_id, **campos)

    def deactivate_institution(self, institucion_id: int) -> Optional[dict]:
        return self.institutions_repo.deactivate_institucion(institucion_id)

    def create_plan(self, **campos) -> dict:
        return self.billing_repo.create_plan(**campos)

    def update_plan(self, plan_id: int, **campos) -> Optional[dict]:
        return self.billing_repo.update_plan(plan_id, **campos)

    def deactivate_plan(self, plan_id: int) -> Optional[dict]:
        return self.billing_repo.deactivate_plan(plan_id)

    def list_members(self, institucion_id: int) -> list[dict]:
        return self.institutions_repo.list_members(institucion_id)

    def add_member(self, institucion_id: int, external_auth_id: str, tipo_miembro: str) -> dict:
        return self.institutions_repo.add_member(institucion_id, external_auth_id, tipo_miembro)

    def deactivate_member(self, membre_id: int) -> dict:
        return self.institutions_repo.deactivate_member(membre_id)

    def list_users(self, auth: Optional[AuthContext] = None) -> list:
        return self.admin_service.list_users(auth)

    def create_user(
        self,
        external_auth_id: str,
        email: str,
        full_name: Optional[str] = None,
        institucion_id: Optional[int] = None,
        tipo_miembro: str = "ESTUDIANTE",
    ) -> UserOut:
        existing = self.users_repository.get_user_by_external_auth_id(external_auth_id)
        if existing:
            raise ValueError("User already exists")
        user = self.users_repository.create_user(
            external_auth_id=external_auth_id,
            email=email,
            role="STUDENT",
            full_name=full_name,
        )
        membership = None
        if institucion_id is not None:
            inst = self.institutions_repo.get_institucion(institucion_id)
            if not inst:
                raise ValueError("Institution not found")
            self.institutions_repo.add_member(institucion_id, external_auth_id, tipo_miembro)
            membership = self.institutions_repo.get_active_membership(external_auth_id)
        return UserOut(
            external_auth_id=user["external_auth_id"],
            email=user.get("email"),
            full_name=user.get("full_name"),
            role=_role_out(user.get("role")),
            institucion_id=(membership or {}).get("institucion_id"),
            tipo_miembro=(membership or {}).get("tipo_miembro"),
            is_platform_admin=False,
            nombre_institucion=(membership or {}).get("nombre_institucion"),
            created_at=_parse_datetime(user["created_at"]),
            updated_at=_parse_datetime(user.get("updated_at") or user["created_at"]),
        )

    def deactivate_user(self, external_auth_id: str) -> bool:
        return self.users_repository.remove_user(external_auth_id)

    def list_platform_admins(self) -> list[dict]:
        return self.users_repository.list_platform_admins()

    def grant_platform_admin(self, external_auth_id: str) -> dict:
        user = self.users_repository.get_user_by_external_auth_id(external_auth_id)
        if not user:
            raise ValueError("User not found")
        admins = self.users_repository.list_platform_admins()
        for admin in admins:
            if admin.get("external_auth_id") == external_auth_id and admin.get("is_active") is not False:
                raise ValueError("User is already a platform admin")
        return self.users_repository.grant_platform_admin(external_auth_id)

    def revoke_platform_admin(self, external_auth_id: str) -> bool:
        return self.users_repository.revoke_platform_admin(external_auth_id)

    def get_metrics(self, auth: Optional[AuthContext] = None, **filters) -> object:
        return self.admin_service.get_metrics(auth, **filters)

    def list_audit_logs(self, auth: Optional[AuthContext] = None, desde: Optional[str] = None, hasta: Optional[str] = None, modelo: Optional[str] = None) -> list[dict]:
        logs = self.audit_repo.list_audit_logs(institucion_id=None)
        if desde or hasta:
            logs = [l for l in logs if (l.get("fecha_evaluacion") or "")[:10] >= (desde or "") and (l.get("fecha_evaluacion") or "")[:10] <= (hasta or "9999-12-31")]
        if modelo:
            logs = [l for l in logs if modelo in (l.get("modelo_ia") or "")]
        return logs
