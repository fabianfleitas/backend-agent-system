from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.security import AuthContext, get_auth_context, get_admin_auth


def make_auth(
    external_auth_id: str = "student-a",
    institucion_id: int = 1,
    tipo_miembro: str = "ESTUDIANTE",
    is_platform_admin: bool = False,
    email: str = None,
    full_name: str = None,
) -> AuthContext:
    return AuthContext(
        external_auth_id=external_auth_id,
        email=email or f"{external_auth_id}@t",
        full_name=full_name or "Test",
        institucion_id=institucion_id,
        tipo_miembro=tipo_miembro,
        is_platform_admin=is_platform_admin,
    )


def build_app_for_routers(*routers, auth: AuthContext = None) -> FastAPI:
    app = FastAPI()
    for r in routers:
        app.include_router(r)
    if auth is not None:
        app.dependency_overrides[get_auth_context] = lambda: auth
        app.dependency_overrides[get_admin_auth] = lambda: auth
    return app
