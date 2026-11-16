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


def pytest_configure(config):
    from app.core.config import settings
    # Desactivar rate limit por defecto en suite; los tests específicos lo activan
    settings.rate_limit_enabled = False


@pytest.fixture(autouse=True)
def _config_get_bool_returns_default(monkeypatch):
    """Hace la resolución de flags de chat determinista (independiente de la DB).

    Los tests unitarios monkeypatchean `settings.*` y esperan que `get_bool`
    devuelva el default (fallback a settings), no el valor de `config_parametros`.
    """
    from app.services.config_service import ConfigService

    monkeypatch.setattr(
        ConfigService,
        "get_bool",
        lambda self, clave, institucion_id=None, default=False: default,
    )
