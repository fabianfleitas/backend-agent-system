from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from fastapi import Header, HTTPException, status, Depends

from app.core.config import settings
from app.repositories.institutions_repository import InstitutionsRepository
from app.repositories.users_repository import UsersRepository


UserType = Literal["ADMIN", "SECRETARIA", "ESTUDIANTE"]


@dataclass(frozen=True)
class AuthContext:
    external_auth_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    institucion_id: Optional[int] = None
    tipo_miembro: Optional[str] = None  # ESTUDIANTE / ADMIN / SECRETARIA
    is_platform_admin: bool = False
    auth_provider: str = "supabase"


def get_auth_context(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> AuthContext:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header (expected Bearer <jwt>)",
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization format (expected Bearer <jwt>)",
        )
    token = parts[1]

    # Verificación de JWT vía Supabase Auth
    try:
        from app.core.supabase import get_supabase_client
        supabase_client = get_supabase_client()
        auth_response = supabase_client.auth.get_user(token)
        supabase_user = auth_response.user
        if not supabase_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired JWT",
            )
        external_auth_id = supabase_user.id  # auth.users.id = sub del JWT
        email = supabase_user.email
        full_name = (supabase_user.user_metadata or {}).get("full_name") or (supabase_user.user_metadata or {}).get("name")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"JWT verification failed: {exc}",
        )

    # Resolver usuario local y validar activo (no confiar en header)
    users_repo = UsersRepository()
    user_row = users_repo.get_user_by_external_auth_id(external_auth_id)
    if not user_row:
        # Creación mínima on-demand para usuario que nunca ha usado el backend
        # El rol no se deriva del JWT; se asigna luego por membresía institucional
        try:
            user_row = users_repo.create_user(
                external_auth_id=external_auth_id,
                email=email or f"{external_auth_id}@supabase.local",
                role="STUDENT",  # deprecado; no determina acceso institucional
                full_name=full_name,
            )
        except Exception:
            # Si falla la creación (race), intentar leer de nuevo
            user_row = users_repo.get_user_by_external_auth_id(external_auth_id)
            if not user_row:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="User persistence unavailable",
                )
    elif user_row.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
        )

    # Resolver membresía institucional (fuente autoritativa para institución)
    institutions_repo = InstitutionsRepository()
    membership = institutions_repo.get_active_membership(external_auth_id)
    is_platform_admin = institutions_repo.is_platform_admin(external_auth_id)

    # Regla: si no es platform_admin y no tiene membresía activa → 403 en negocio
    # Pero /me debe funcionar (se valida en la ruta o con otra política)
    # Aquí construimos el contexto; los endpoints deciden si requieren miembro
    return AuthContext(
        external_auth_id=external_auth_id,
        email=email,
        full_name=full_name,
        institucion_id=membership.get("institucion_id") if membership else None,
        tipo_miembro=membership.get("tipo_miembro") if membership else None,
        is_platform_admin=is_platform_admin,
        auth_provider="supabase",
    )


def require_member(auth: AuthContext) -> AuthContext:
    if auth.is_platform_admin:
        return auth  # SUPERADMIN bypass para /platform/*; para /admin/* debe validar también
    if not auth.institucion_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Institution membership required",
        )
    return auth


def require_institution_admin(auth: AuthContext) -> AuthContext:
    # Platform admin sin membresía institucional NO debe acceder a /admin/*
    # (solo /platform/*). Si tiene membresía, funciona normalmente.
    if not auth.institucion_id:
        if auth.is_platform_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform admin must have institution membership for /admin/*; use /platform/* instead",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Institution membership required",
        )
    if auth.tipo_miembro not in ("ADMIN", "SECRETARIA"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for institution",
        )
    return auth


def get_admin_auth(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    return require_institution_admin(auth)


def require_platform_admin(auth: AuthContext) -> AuthContext:
    if not auth.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    return auth
