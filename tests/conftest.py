from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat import routes as chat_routes
from app.core.security import AuthContext, get_auth_context


def make_auth(
    external_auth_id: str = "student-1",
    institucion_id: int = 1,
    tipo_miembro: str = "ESTUDIANTE",
    is_platform_admin: bool = False,
    email: str = None,
    full_name: str = None,
) -> AuthContext:
    return AuthContext(
        external_auth_id=external_auth_id,
        email=email,
        full_name=full_name,
        institucion_id=institucion_id,
        tipo_miembro=tipo_miembro,
        is_platform_admin=is_platform_admin,
    )


def override_auth(app: FastAPI, auth: AuthContext) -> None:
    app.dependency_overrides[get_auth_context] = lambda: auth
