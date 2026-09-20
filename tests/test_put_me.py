from __future__ import annotations

"""Tests para PUT /me (edición de perfil)."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.core.security import AuthContext, get_auth_context
from app.services.users_service import UsersService


def _admin_auth() -> AuthContext:
    return AuthContext(external_auth_id="a", email="a@t", institucion_id=1, tipo_miembro="ADMIN")


def test_put_me_updates_full_name(monkeypatch):
    app = create_app()
    app.dependency_overrides[get_auth_context] = lambda: _admin_auth()

    class FakeUsersService:
        def update_current_user(self, auth, full_name=None):
            assert auth.external_auth_id == "a"
            assert full_name == "Nuevo nombre"
            return {
                "external_auth_id": auth.external_auth_id,
                "email": "a@t",
                "full_name": full_name,
                "role": "ADMIN",
                "institucion_id": 1,
                "tipo_miembro": "ADMIN",
                "is_platform_admin": False,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            }

    monkeypatch.setattr("app.main.UsersService", lambda: FakeUsersService())
    resp = TestClient(app).put("/me", json={"full_name": "Nuevo nombre"})
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Nuevo nombre"


def test_put_me_requires_auth():
    app = create_app()
    resp = TestClient(app).put("/me", json={"full_name": "X"})
    assert resp.status_code == 401


def test_put_me_service_updates(monkeypatch):
    class FakeRepo:
        def __init__(self):
            self.called = None

        def update_user(self, external_auth_id, full_name=None):
            self.called = (external_auth_id, full_name)
            return {
                "external_auth_id": external_auth_id,
                "email": "a@t",
                "full_name": full_name,
                "role": "ADMIN",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            }

    class FakeInstRepo:
        def get_active_membership(self, eid):
            return {"institucion_id": 1, "tipo_miembro": "ADMIN"}

        def is_platform_admin(self, eid):
            return False

    monkeypatch.setattr("app.repositories.institutions_repository.InstitutionsRepository", lambda: FakeInstRepo())
    repo = FakeRepo()
    svc = UsersService(repository=repo)
    out = svc.update_current_user(_admin_auth(), full_name="Nuevo")
    assert repo.called == ("a", "Nuevo")
    assert out.full_name == "Nuevo"
    assert out.tipo_miembro == "ADMIN"