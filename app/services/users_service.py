from __future__ import annotations

from datetime import datetime
import re
from typing import Optional

from app.core.security import AuthContext
from app.repositories.users_repository import UsersRepository
from app.schemas.common import UserOut, UserRole


class UsersService:
    def __init__(self, repository: Optional[UsersRepository] = None) -> None:
        self.repository = repository or UsersRepository()

    def get_or_create_current_user(self, auth: AuthContext) -> UserOut:
        user = self.repository.get_or_create_user(auth)
        return self._user_out(user, auth)

    def update_current_user(self, auth: AuthContext, full_name: Optional[str] = None) -> UserOut:
        user = self.repository.update_user(auth.external_auth_id, full_name=full_name)
        if not user:
            user = self.repository.get_or_create_user(auth)
        return self._user_out(user, auth)

    def _user_out(self, user: dict, auth: AuthContext) -> UserOut:
        # Resolver membresía institucional para completar UserOut
        from app.repositories.institutions_repository import InstitutionsRepository
        inst_repo = InstitutionsRepository()
        membership = inst_repo.get_active_membership(auth.external_auth_id)
        return UserOut(
            external_auth_id=user["external_auth_id"],
            email=user.get("email"),
            full_name=user.get("full_name"),
            role=_role_out(user.get("role")),
            institucion_id=membership.get("institucion_id") if membership else None,
            tipo_miembro=membership.get("tipo_miembro") if membership else None,
            is_platform_admin=inst_repo.is_platform_admin(auth.external_auth_id),
            created_at=_parse_datetime(user["created_at"]),
            updated_at=_parse_datetime(user.get("updated_at") or user["created_at"]),
        )


def _role_out(role: Optional[str]) -> UserRole:
    mapping = {"ADMIN": UserRole.ADMIN, "STAFF": UserRole.STAFF, "STUDENT": UserRole.STUDENT}
    return mapping.get(role or "", UserRole.STUDENT)


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    normalized = value.replace("Z", "+00:00")
    match = re.search(r"\.(\d+)([+-]\d{2}:\d{2})$", normalized)
    if match:
        fraction, offset = match.groups()
        normalized = normalized.replace(f".{fraction}{offset}", f".{fraction.ljust(6, '0')[:6]}{offset}")
    return datetime.fromisoformat(normalized)
