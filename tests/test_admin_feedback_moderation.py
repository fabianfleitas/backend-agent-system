from __future__ import annotations

"""Tests para DELETE /api/admin/feedback/{id} (moderación: ocultar con is_active)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_auth_context
from app.services.admin_service import AdminService


def _make_app(auth: AuthContext):
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_auth_context] = lambda: auth
    return app


def _admin() -> AuthContext:
    return AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN")


class _Dummy:
    def __getattr__(self, _name):
        return lambda *a, **k: []


class FakeService:
    def __init__(self, ok=True):
        self.ok = ok

    def deactivate_feedback(self, auth=None, feedback_id=None):
        return self.ok


# --- Route level ---

def test_deactivate_feedback_204(monkeypatch):
    app = _make_app(_admin())
    monkeypatch.setattr("app.api.admin.routes.AdminService", lambda: FakeService(ok=True))
    resp = TestClient(app).delete("/api/admin/feedback/1")
    assert resp.status_code == 204


def test_deactivate_feedback_404_when_missing(monkeypatch):
    app = _make_app(_admin())
    monkeypatch.setattr("app.api.admin.routes.AdminService", lambda: FakeService(ok=False))
    resp = TestClient(app).delete("/api/admin/feedback/99")
    assert resp.status_code == 404


def test_deactivate_feedback_403_for_estudiante():
    auth = AuthContext(external_auth_id="s", institucion_id=1, tipo_miembro="ESTUDIANTE")
    app = _make_app(auth)
    resp = TestClient(app).delete("/api/admin/feedback/1")
    assert resp.status_code == 403


def test_deactivate_feedback_403_platform_admin_without_membership():
    auth = AuthContext(external_auth_id="pa", institucion_id=None, tipo_miembro=None, is_platform_admin=True)
    app = _make_app(auth)
    resp = TestClient(app).delete("/api/admin/feedback/1")
    assert resp.status_code == 403


# --- Service level: aislamiento por institución y filtro de inactivos ---

class FakeFeedbackRepo:
    def __init__(self):
        self.deactivated = []

    def deactivate_feedback(self, feedback_id, institucion_id):
        # Simula aislamiento: solo el feedback de la institución B (id 2)
        if institucion_id == 2 and feedback_id == 10:
            self.deactivated.append(feedback_id)
            return {"id": feedback_id, "is_active": False}
        return None

    def list_feedback(self, institucion_id, **kwargs):
        return []


def test_deactivate_feedback_scoped_by_institution():
    repo = FakeFeedbackRepo()
    svc = AdminService(users_repository=_Dummy(), metrics_repository=_Dummy(), feedback_repository=repo)
    assert svc.deactivate_feedback(AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN"), feedback_id=10) is False
    assert svc.deactivate_feedback(AuthContext(external_auth_id="b", institucion_id=2, tipo_miembro="ADMIN"), feedback_id=10) is True
    assert repo.deactivated == [10]


def test_deactivate_feedback_blocked_for_platform_admin():
    repo = FakeFeedbackRepo()
    svc = AdminService(users_repository=_Dummy(), metrics_repository=_Dummy(), feedback_repository=repo)
    assert svc.deactivate_feedback(AuthContext(external_auth_id="pa", institucion_id=None, is_platform_admin=True), feedback_id=10) is False