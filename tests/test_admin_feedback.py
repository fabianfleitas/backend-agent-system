from __future__ import annotations

"""Tests para GET /api/admin/feedback (moderación global de feedback)."""

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


class FakeAdminService:
    def __init__(self, rows):
        self._rows = rows

    def list_feedback(self, auth, conversacion_id=None, message_id=None, rating=None):
        return self._rows


def _admin() -> AuthContext:
    return AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN")


def test_admin_feedback_paginated(monkeypatch):
    app = _make_app(_admin())
    rows = [
        {"id": 1, "message_id": 10, "rating": 5, "comment": "ok", "external_auth_id": "u1",
         "audit_id": "aaa", "created_at": "2026-01-01T00:00:00Z",
         "mensajes": {"conversacion_id": 7, "contenido_texto": "pregunta"}},
        {"id": 2, "message_id": 11, "rating": 2, "comment": None, "external_auth_id": "u2",
         "audit_id": "bbb", "created_at": "2026-01-02T00:00:00Z",
         "mensajes": {"conversacion_id": 8, "contenido_texto": "otra"}},
    ]
    monkeypatch.setattr("app.api.admin.routes.AdminService", lambda: FakeAdminService(rows))
    resp = TestClient(app).get("/api/admin/feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pagination"]["total"] == 2
    assert data["items"][0]["conversacion_id"] == 7
    assert data["items"][0]["contenido_texto"] == "pregunta"
    assert data["items"][0]["rating"] == 5


def test_admin_feedback_blocks_platform_admin_without_membership(monkeypatch):
    auth = AuthContext(external_auth_id="pa", institucion_id=None, tipo_miembro=None, is_platform_admin=True)
    app = _make_app(auth)
    monkeypatch.setattr("app.api.admin.routes.AdminService", lambda: FakeAdminService([]))
    resp = TestClient(app).get("/api/admin/feedback")
    assert resp.status_code == 403


class FakeFeedbackRepo:
    def __init__(self):
        self.captured = {}

    def list_feedback(self, institucion_id, conversacion_id=None, message_id=None, rating=None):
        self.captured = {
            "institucion_id": institucion_id,
            "conversacion_id": conversacion_id,
            "message_id": message_id,
            "rating": rating,
        }
        return []


class _Dummy:
    def __getattr__(self, _name):
        return lambda *a, **k: []


def test_admin_feedback_service_filters_by_institution():
    repo = FakeFeedbackRepo()
    svc = AdminService(users_repository=_Dummy(), metrics_repository=_Dummy(), feedback_repository=repo)
    result = svc.list_feedback(
        AuthContext(external_auth_id="a", institucion_id=5, tipo_miembro="ADMIN"),
        conversacion_id=7,
        rating=4,
    )
    assert result == []
    assert repo.captured["institucion_id"] == 5
    assert repo.captured["conversacion_id"] == 7
    assert repo.captured["rating"] == 4


def test_admin_feedback_service_platform_admin_returns_empty():
    repo = FakeFeedbackRepo()
    svc = AdminService(users_repository=_Dummy(), metrics_repository=_Dummy(), feedback_repository=repo)
    result = svc.list_feedback(
        AuthContext(external_auth_id="pa", institucion_id=None, tipo_miembro=None, is_platform_admin=True)
    )
    assert result == []
    assert repo.captured == {}