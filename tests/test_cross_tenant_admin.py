from __future__ import annotations

"""C2 — Tests cross-tenant de rutas (audit/config/categories/users/metrics/billing/audio/feedback).

Con auth de la institución A, ningún recurso de la institución B debe aparecer:
- listas → 200 con items vacíos (sin fuga)
- recurso único (audio / detalle) → 404
- feedback sobre mensaje ajeno → 404

Patrón: router + dependency_overrides de auth + fakes "tenant-guardados" que solo
devuelven datos si auth.institucion_id == TARGET (emula el filtrado real por repo).
"""

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.api.admin.routes import router as admin_router
from app.api.admin.categories_routes import router as categories_router
from app.api.chat.routes import router as chat_router, _get_audio_service, _get_chat_service
from app.core.security import AuthContext, get_auth_context
from app.schemas.system import MetricsOut

TARGET = 2  # institución B (los datos "pertenecen" a B)


def _auth_a() -> AuthContext:
    return AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN")


def _auth_b() -> AuthContext:
    return AuthContext(external_auth_id="b", institucion_id=TARGET, tipo_miembro="ADMIN")


def _make_app(auth: AuthContext):
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    app.include_router(categories_router, prefix="/api/admin")
    app.include_router(chat_router, prefix="/api/chat")
    app.dependency_overrides[get_auth_context] = lambda: auth
    return app


def _guard(auth) -> bool:
    return getattr(auth, "institucion_id", None) == TARGET


class FakeAdminService:
    def list_users(self, auth):
        return [] if not _guard(auth) else []

    def get_metrics(self, auth, **kw):
        return MetricsOut(total_queries=1) if _guard(auth) else MetricsOut()

    def list_feedback(self, auth, **kw):
        return [] if not _guard(auth) else []


class FakeAuditService:
    def list_audit_logs(self, auth):
        return [] if not _guard(auth) else []


class FakeDocsService:
    def list_documents(self, auth):
        return [] if not _guard(auth) else []

    def get_document(self, documento_id, auth):
        return None if not _guard(auth) else ({"id": documento_id, "titulo": "Doc B", "activo": True, "fecha_creacion": "2026-01-01T00:00:00Z"}, [])


class FakeBilling:
    def get_subscription(self, auth=None):
        return None if not _guard(auth) else {"id": 1, "plan_id": 1}

    def get_subscription_history(self, auth=None, suscripcion_id=None):
        return [] if not _guard(auth) else []

    def get_plan_for_subscription(self, auth=None):
        return None if not _guard(auth) else {"id": 1, "nombre": "Plan B"}

    def list_plans_for_admin(self):
        return []

    def list_pagos(self, auth=None):
        return [] if not _guard(auth) else []

    def list_comprobantes(self, auth=None):
        return [] if not _guard(auth) else []


class FakeCategoriesService:
    def list_by_institution(self, auth):
        return [] if not _guard(auth) else []


class FakeConfigRepo:
    def list_by_institution(self, inst_id):
        return [] if inst_id != TARGET else []

    def list_params(self):
        return []


class FakeAudioService:
    def get_response_audio(self, audio_interaction_id, auth):
        return None if not _guard(auth) else (b"audio", "audio/webm")


class FakeChatService:
    def create_feedback(self, auth, message_id, rating, comment, audit_id):
        return None if not _guard(auth) else {"id": 1, "message_id": message_id, "rating": rating, "comment": comment, "audit_id": audit_id, "created_at": "2026-01-01T00:00:00Z"}


def _apply_fakes(monkeypatch, app: FastAPI):
    monkeypatch.setattr("app.api.admin.routes.AdminService", lambda: FakeAdminService())
    monkeypatch.setattr("app.api.admin.routes.AuditService", lambda: FakeAuditService())
    monkeypatch.setattr("app.api.admin.routes.DocumentsService", lambda: FakeDocsService())
    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: FakeBilling())
    monkeypatch.setattr("app.services.billing_service.BillingService", lambda: FakeBilling())
    monkeypatch.setattr("app.api.admin.categories_routes.CategoriesService", lambda: FakeCategoriesService())
    monkeypatch.setattr("app.repositories.config_repository.ConfigParametersRepository", lambda: FakeConfigRepo())
    monkeypatch.setattr("app.api.chat.routes._get_chat_service", lambda: FakeChatService())
    app.dependency_overrides[_get_audio_service] = lambda: FakeAudioService()


# --- Negativos: auth A no ve recursos de B ---

def test_cross_tenant_lists_empty(monkeypatch):
    app = _make_app(_auth_a())
    _apply_fakes(monkeypatch, app)
    client = TestClient(app)
    for path in [
        "/api/admin/documents",
        "/api/admin/audit",
        "/api/admin/users",
        "/api/admin/feedback",
        "/api/admin/config",
        "/api/admin/categories",
        "/api/admin/subscription/history",
        "/api/admin/pagos",
        "/api/admin/comprobantes",
        "/api/admin/plans",
    ]:
        resp = client.get(path)
        assert resp.status_code == 200, path
        body = resp.json()
        if isinstance(body, list):
            assert body == [], path
        else:
            assert body.get("items") == [] or body.get("total") == 0, path


def test_cross_tenant_metrics_empty(monkeypatch):
    app = _make_app(_auth_a())
    _apply_fakes(monkeypatch, app)
    client = TestClient(app)
    resp = client.get("/api/admin/metrics")
    assert resp.status_code == 200
    assert resp.json()["total_queries"] == 0


def test_cross_tenant_single_resources_404(monkeypatch):
    app = _make_app(_auth_a())
    _apply_fakes(monkeypatch, app)
    client = TestClient(app)
    assert client.get("/api/admin/documents/99").status_code == 404
    assert client.get("/api/admin/subscription").status_code == 404
    assert client.get("/api/admin/plan").status_code == 404
    assert client.get("/api/chat/audio/99").status_code == 404


def test_cross_tenant_feedback_post_404(monkeypatch):
    app = _make_app(_auth_a())
    _apply_fakes(monkeypatch, app)
    client = TestClient(app)
    resp = client.post(
        "/api/chat/feedback",
        json={"message_id": 10, "rating": 5, "comment": "ok", "audit_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert resp.status_code == 404


# --- Controles positivos: auth B (misma institución de los datos) sí los ve ---

def test_matching_institution_sees_data(monkeypatch):
    app = _make_app(_auth_b())
    _apply_fakes(monkeypatch, app)
    client = TestClient(app)
    assert client.get("/api/admin/metrics").json()["total_queries"] == 1
    assert client.get("/api/admin/subscription").status_code == 200
    assert client.get("/api/admin/plan").status_code == 200
    assert client.get("/api/admin/documents/99").status_code == 200
    audio = client.get("/api/chat/audio/99")
    assert audio.status_code == 200
    assert audio.content == b"audio"
    fb = client.post(
        "/api/chat/feedback",
        json={"message_id": 10, "rating": 5, "comment": "ok", "audit_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert fb.status_code == 200
    assert fb.json()["message_id"] == 10