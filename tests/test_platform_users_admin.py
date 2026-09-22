from __future__ import annotations

"""C5 — CRUD de usuarios y gestión de platform_admins en /api/platform/* (platform admin).

Cubre: guards (403 para admin institucional), creación/desactivación de usuarios,
alta/baja de platform admins, manejo de conflictos (409) y cascada de desactivación.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.platform.routes import router as platform_router, _get_plat_service
from app.core.security import AuthContext, get_auth_context


def _make_app(auth: AuthContext, fake_service):
    app = FastAPI()
    app.include_router(platform_router, prefix="/api/platform")
    app.dependency_overrides[get_auth_context] = lambda: auth
    app.dependency_overrides[_get_plat_service] = lambda: fake_service
    return app


def _platform_auth() -> AuthContext:
    return AuthContext(external_auth_id="pa", institucion_id=None, tipo_miembro=None, is_platform_admin=True)


def _institution_admin() -> AuthContext:
    return AuthContext(external_auth_id="ia", institucion_id=1, tipo_miembro="ADMIN")


USER = {
    "external_auth_id": "u1",
    "email": "u1@example.com",
    "full_name": "Usuario Uno",
    "role": "STUDENT",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}

PLATFORM_ADMIN = {
    "external_auth_id": "admin-x",
    "email": "admin@example.com",
    "full_name": "Admin X",
    "is_active": True,
    "created_at": "2026-01-01T00:00:00Z",
}


class FakePlatformService:
    def __init__(self):
        self.calls = []

    def create_user(self, external_auth_id, email, full_name=None, institucion_id=None, tipo_miembro="ESTUDIANTE"):
        self.calls.append(("create_user", external_auth_id, institucion_id))
        if external_auth_id == "exists":
            raise ValueError("User already exists")
        return _user_out(external_auth_id, email, full_name, institucion_id, tipo_miembro)

    def deactivate_user(self, external_auth_id):
        self.calls.append(("deactivate_user", external_auth_id))
        return external_auth_id != "missing"

    def list_platform_admins(self):
        self.calls.append(("list_platform_admins",))
        return [dict(PLATFORM_ADMIN)]

    def grant_platform_admin(self, external_auth_id):
        self.calls.append(("grant_platform_admin", external_auth_id))
        if external_auth_id == "dup":
            raise ValueError("User is already a platform admin")
        if external_auth_id == "missing":
            raise ValueError("User not found")
        return dict(PLATFORM_ADMIN, external_auth_id=external_auth_id)

    def revoke_platform_admin(self, external_auth_id):
        self.calls.append(("revoke_platform_admin", external_auth_id))
        return external_auth_id != "missing"


def _user_out(eid, email, full_name, institucion_id, tipo_miembro):
    from datetime import datetime
    from app.schemas.common import UserOut, UserRole
    return UserOut(
        external_auth_id=eid,
        email=email,
        full_name=full_name,
        role=UserRole.STUDENT,
        institucion_id=institucion_id,
        tipo_miembro=tipo_miembro,
        is_platform_admin=False,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )


# --- Guards ---

def test_users_admin_blocks_institutional_admin():
    app = _make_app(_institution_admin(), FakePlatformService())
    client = TestClient(app)
    assert client.post("/api/platform/users", json={"external_auth_id": "n", "email": "n@x.com"}).status_code == 403
    assert client.delete("/api/platform/users/u1").status_code == 403
    assert client.get("/api/platform/admins").status_code == 403
    assert client.post("/api/platform/admins", json={"external_auth_id": "x"}).status_code == 403
    assert client.delete("/api/platform/admins/x").status_code == 403


# --- Users CRUD ---

def test_create_user(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    resp = TestClient(app).post(
        "/api/platform/users",
        json={"external_auth_id": "u9", "email": "u9@example.com", "full_name": "Nueve", "institucion_id": 1, "tipo_miembro": "ADMIN"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["external_auth_id"] == "u9"
    assert body["institucion_id"] == 1
    assert body["tipo_miembro"] == "ADMIN"
    assert svc.calls[0][0] == "create_user"


def test_create_user_conflict_409(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    resp = TestClient(app).post("/api/platform/users", json={"external_auth_id": "exists", "email": "e@x.com"})
    assert resp.status_code == 409


def test_deactivate_user(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    assert TestClient(app).delete("/api/platform/users/u1").status_code == 204
    assert TestClient(app).delete("/api/platform/users/missing").status_code == 404


# --- Platform admins ---

def test_list_platform_admins(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    resp = TestClient(app).get("/api/platform/admins")
    assert resp.status_code == 200
    assert resp.json()[0]["external_auth_id"] == "admin-x"
    assert resp.json()[0]["email"] == "admin@example.com"
    assert resp.json()[0]["is_active"] is True


def test_grant_platform_admin(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    resp = TestClient(app).post("/api/platform/admins", json={"external_auth_id": "new-admin"})
    assert resp.status_code == 201
    assert resp.json()["external_auth_id"] == "new-admin"
    assert svc.calls[0][0] == "grant_platform_admin"


def test_grant_platform_admin_conflict_409(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    assert TestClient(app).post("/api/platform/admins", json={"external_auth_id": "dup"}).status_code == 409


def test_revoke_platform_admin(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    assert TestClient(app).delete("/api/platform/admins/admin-x").status_code == 204
    assert TestClient(app).delete("/api/platform/admins/missing").status_code == 404


# --- Service level: cascada de desactivación y fix de get_memberships_batch ---

def test_platform_service_deactivate_user_cascades():
    calls = {}

    class FakeUsersRepo:
        def remove_user(self, external_auth_id):
            calls["target"] = external_auth_id
            return external_auth_id == "u1"

    from app.services.platform_service import PlatformService
    svc = PlatformService(institutions_repo=object(), audit_repo=object(), admin_service=object(), billing_repo=object(), users_repository=FakeUsersRepo())
    assert svc.deactivate_user("u1") is True
    assert calls["target"] == "u1"


def test_get_memberships_batch_uses_is_active_column():
    """El fix del bug: get_memberships_batch debe consultar la columna real
    `platform_admins.is_active`, no la inexistente `is_platform_admin`."""
    recorded = {}
    import json

    class FakeResp:
        def __init__(self, data):
            self.data = data

    class FakeClient:
        def table(self, name):
            return FakeQuery(recorded, name)

        @property
        def data(self):
            return []

    class FakeQuery:
        def __init__(self, recorder, name):
            self.recorder = recorder
            self.name = name

        def select(self, cols):
            self.recorder["select"] = cols
            return self

        def in_(self, col, vals):
            self.recorder["in_"] = (col, vals)
            return self

        def eq(self, col, val):
            self.recorder["eq"] = (col, val)
            return self

        def limit(self, n):
            return self

        def order(self, col, desc=False):
            return self

        def execute(self):
            if self.name == "institucion_miembros":
                return FakeResp([])
            return FakeResp([{"external_auth_id": "pa"}])

    from app.repositories.users_repository import UsersRepository
    repo = UsersRepository(client=FakeClient())
    result = repo.get_memberships_batch(["pa"])
    # El fix: la consulta a platform_admins usa is_active, no is_platform_admin
    assert recorded["select"].startswith("external_auth_id, is_active") or "is_active" in recorded["select"]
    assert recorded["eq"] == ("is_active", True)
    assert result.get("pa", {}).get("is_platform_admin") is True