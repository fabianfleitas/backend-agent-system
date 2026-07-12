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
        return UserOut(
            external_auth_id=user["external_auth_id"],
            email=user.get("email"),
            role=_role_out(user.get("role")),
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
