from __future__ import annotations

"""Tests para exportaciones CSV de platform (GET /api/platform/{audit,comprobantes,metrics}/export)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.platform.routes import router as platform_router
from app.core.security import AuthContext, get_auth_context
from app.schemas.system import MetricsOut


def _make_app(auth: AuthContext):
    app = FastAPI()
    app.include_router(platform_router, prefix="/api/platform")
    app.dependency_overrides[get_auth_context] = lambda: auth
    return app


def _platform() -> AuthContext:
    return AuthContext(external_auth_id="pa", institucion_id=None, tipo_miembro=None, is_platform_admin=True)


class FakePlatformService:
    def list_audit_logs(self, auth, desde=None, hasta=None, modelo=None):
        return [{"id": "abc", "mensaje_id": 1, "observaciones": "LLM: x [text]"}]

    def get_metrics(self, auth, **kw):
        return MetricsOut(total_queries=1)


def test_platform_export_audit_csv(monkeypatch):
    app = _make_app(_platform())
    monkeypatch.setattr("app.api.platform.routes.PlatformService", lambda: FakePlatformService())
    resp = TestClient(app).get("/api/platform/audit/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "observaciones" in resp.text


def test_platform_export_metrics_csv(monkeypatch):
    app = _make_app(_platform())
    monkeypatch.setattr("app.api.platform.routes.PlatformService", lambda: FakePlatformService())
    resp = TestClient(app).get("/api/platform/metrics/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "AGREGADOS" in resp.text


def test_platform_export_comprobantes_csv(monkeypatch):
    app = _make_app(_platform())
    monkeypatch.setattr(
        "app.repositories.billing_repository.BillingRepository",
        lambda: type("B", (), {"list_comprobantes": lambda self: [{"id": 1, "tipo_comprobante": "FACTURA"}]})(),
    )
    resp = TestClient(app).get("/api/platform/comprobantes/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "tipo_comprobante" in resp.text


def test_platform_export_blocks_institutional_admin():
    auth = AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN")
    app = _make_app(auth)
    assert TestClient(app).get("/api/platform/audit/export").status_code == 403