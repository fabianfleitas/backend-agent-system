from __future__ import annotations

"""C1 — Un platform admin sin membresía institucional NO debe acceder a /api/admin/*.

El guard require_institution_admin corta (403) antes de tocar repos/DB, por lo que
los tests de rutas reales no requieren fakes de servicios para el caso negativo.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_auth_context


def _make_app(auth: AuthContext):
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_auth_context] = lambda: auth
    return app


PLATFORM_WITHOUT_MEMBERSHIP = AuthContext(
    external_auth_id="pa",
    institucion_id=None,
    tipo_miembro=None,
    is_platform_admin=True,
)


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/admin/documents"),
    ("GET", "/api/admin/metrics"),
    ("GET", "/api/admin/audit"),
    ("GET", "/api/admin/users"),
    ("GET", "/api/admin/config"),
    ("GET", "/api/admin/feedback"),
    ("GET", "/api/admin/plans"),
])
def test_platform_admin_without_membership_blocked(method, path):
    app = _make_app(PLATFORM_WITHOUT_MEMBERSHIP)
    resp = TestClient(app).request(method, path)
    assert resp.status_code == 403
    assert "must have institution membership" in resp.json().get("detail", "")


def test_platform_admin_with_membership_allowed(monkeypatch):
    auth = AuthContext(external_auth_id="pa", institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=True)
    app = _make_app(auth)

    class FakeAdminService:
        def list_feedback(self, auth, conversacion_id=None, message_id=None, rating=None):
            return []

    monkeypatch.setattr("app.api.admin.routes.AdminService", lambda: FakeAdminService())
    resp = TestClient(app).get("/api/admin/feedback")
    assert resp.status_code == 200