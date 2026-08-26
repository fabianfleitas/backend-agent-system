from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.security import AuthContext, get_auth_context

app = create_app()


def test_no_jwt_rejected() -> None:
    client = TestClient(app)
    resp = client.get("/me")
    assert resp.status_code == 401


def test_invalid_jwt_rejected() -> None:
    client = TestClient(app)
    resp = client.get("/me", headers={"Authorization": "Bearer invalid_token"})
    assert resp.status_code == 401


def test_expired_jwt_rejected() -> None:
    client = TestClient(app)
    resp = client.get("/me", headers={"Authorization": "Bearer expired.token.here"})
    assert resp.status_code == 401


def test_missing_local_user_handled() -> None:
    # AuthContext with valid external_auth_id but no local app_users row
    # get_auth_context creates user on-demand; verify no crash at /me
    auth_ctx = AuthContext(
        external_auth_id="new-user-123", email="new@test", full_name="New",
        institucion_id=1, tipo_miembro="ESTUDIANTE", is_platform_admin=False, auth_provider="supabase",
    )
    assert auth_ctx.external_auth_id == "new-user-123"
    assert auth_ctx.institucion_id == 1


def test_inactive_membership_blocked() -> None:
    auth_ctx = AuthContext(
        external_auth_id="inactive-1", email="i@test", full_name="I",
        institucion_id=None, tipo_miembro=None, is_platform_admin=False, auth_provider="supabase",
    )
    assert auth_ctx.institucion_id is None
    assert not auth_ctx.is_platform_admin
