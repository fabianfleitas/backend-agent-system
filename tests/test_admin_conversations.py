from __future__ import annotations

"""Tests del endpoint GET /api/admin/conversations (CU-22, conversaciones institucionales).

Cubre:
- 200 admin con membresía: listado paginado con message_count y external_auth_id
- include_hidden=True incluye ocultas; False no
- 403 platform admin sin membresía institucional (get_admin_auth)
- aislamiento cross-tenant: datos de otra institución no se listan
"""

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_auth_context

TARGET = 1


def _conv(conv_id, institucion_id, hidden=False):
    return {
        "id": conv_id,
        "title": f"Conv {conv_id}",
        "institucion_id": institucion_id,
        "hidden": hidden,
        "external_auth_id": f"user-{conv_id}",
        "last_interaction": "2026-01-01T10:00:00Z",
    }


def _make_app(auth: AuthContext):
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_auth_context] = lambda: auth
    return app


class FakeConversationsService:
    def __init__(self, data):
        self.data = data

    def list_institution_conversations(self, institucion_id, include_hidden=False):
        rows = [c for c in self.data if c.get("institucion_id") == institucion_id]
        if not include_hidden:
            rows = [c for c in rows if not c.get("hidden")]
        return rows

    def count_messages(self, conversation_id):
        return 3


def test_admin_conversations_200_paginated(monkeypatch):
    monkeypatch.setattr(
        "app.api.admin.routes.ConversationsService",
        lambda: FakeConversationsService(
            [
                _conv(1, TARGET),
                _conv(2, TARGET),
                _conv(3, 999),  # otra institución, no debe listarse
                _conv(4, TARGET, hidden=True),
            ]
        ),
    )
    app = _make_app(AuthContext(external_auth_id="a", institucion_id=TARGET, tipo_miembro="ADMIN"))
    client = TestClient(app)
    resp = client.get("/api/admin/conversations", params={"limit": 10, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["total"] == 2
    ids = {item["id"] for item in body["items"]}
    assert ids == {1, 2}
    assert body["items"][0]["message_count"] == 3
    assert body["items"][0]["external_auth_id"]


def test_admin_conversations_include_hidden(monkeypatch):
    monkeypatch.setattr(
        "app.api.admin.routes.ConversationsService",
        lambda: FakeConversationsService([_conv(1, TARGET), _conv(4, TARGET, hidden=True)]),
    )
    app = _make_app(AuthContext(external_auth_id="a", institucion_id=TARGET, tipo_miembro="ADMIN"))
    client = TestClient(app)
    hidden = client.get("/api/admin/conversations", params={"include_hidden": True}).json()
    assert {item["id"] for item in hidden["items"]} == {1, 4}
    visible = client.get("/api/admin/conversations").json()
    assert {item["id"] for item in visible["items"]} == {1}


def test_admin_conversations_403_platform_without_membership(monkeypatch):
    monkeypatch.setattr("app.api.admin.routes.ConversationsService", lambda: FakeConversationsService([]))
    app = _make_app(AuthContext(external_auth_id="p", institucion_id=None, is_platform_admin=True))
    client = TestClient(app)
    assert client.get("/api/admin/conversations").status_code == 403
    assert client.get("/api/admin/conversations", params={"include_hidden": True}).status_code == 403


def test_admin_conversations_cross_tenant_empty(monkeypatch):
    monkeypatch.setattr(
        "app.api.admin.routes.ConversationsService",
        lambda: FakeConversationsService([_conv(5, 999), _conv(6, 999)]),
    )
    app = _make_app(AuthContext(external_auth_id="a", institucion_id=TARGET, tipo_miembro="ADMIN"))
    client = TestClient(app)
    body = client.get("/api/admin/conversations").json()
    assert body["items"] == []
    assert body["pagination"]["total"] == 0