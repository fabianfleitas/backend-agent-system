from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from fastapi import Header, HTTPException, status


UserType = Literal["ADMIN", "SECRETARIA", "ESTUDIANTE"]


@dataclass(frozen=True)
class AuthContext:
    external_auth_id: str
    auth_provider: str
    tipo_usuario: UserType
    correo: Optional[str] = None


def get_auth_context(
    x_external_auth_id: Optional[str] = Header(default=None, alias="X-External-Auth-Id"),
    x_auth_provider: str = Header(default="delegated", alias="X-Auth-Provider"),
    x_user_type: UserType = Header(default="ESTUDIANTE", alias="X-User-Type"),
    x_user_email: Optional[str] = Header(default=None, alias="X-User-Email"),
) -> AuthContext:
    if not x_external_auth_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-External-Auth-Id header",
        )
    return AuthContext(
        external_auth_id=x_external_auth_id,
        auth_provider=x_auth_provider,
        tipo_usuario=x_user_type,
        correo=x_user_email,
    )


def require_admin(auth: AuthContext) -> AuthContext:
    if auth.tipo_usuario not in ("ADMIN", "SECRETARIA"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return auth
