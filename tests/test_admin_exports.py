from __future__ import annotations

"""Tests para exportaciones CSV (GET /api/admin/{audit,comprobantes,metrics}/export)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_auth_context
from app.schemas.system import MetricsOut


def _make_app(auth: AuthContext):
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_auth_context] = lambda: auth
    return app


def _admin() -> AuthContext:
    return AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN")


class FakeAuditService:
    def list_audit_logs(self, auth=None):
        return [{"id": "abc", "mensaje_id": 1, "observaciones": "LLM: x [text]", "fecha_evaluacion": "2026-01-01T00:00:00Z"}]


class FakeBilling:
    def list_comprobantes(self, auth=None):
        return [{"id": 1, "institucion_id": 1, "tipo_comprobante": "FACTURA", "numero": "A001", "importe": 10.0, "moneda": "USD", "fecha_emision": "2026-01-01"}]


class FakeAdminService:
    def get_metrics(self, auth, **kw):
        return MetricsOut(
            total_queries=2,
            total_conversations=1,
            tokens_by_model={"openai/gpt-4o-mini": {"input": 5, "output": 2}},
            top_documents=[{"documento_id": 10, "titulo": "Reglamento", "consultas": 1}],
            series=[{"fecha": "2026-01-01", "conversaciones": 1, "tokens_input": 5, "tokens_output": 2, "llm": 1, "guard": 0, "llm_failed": 0}],
        )


def test_export_audit_csv(monkeypatch):
    app = _make_app(_admin())
    monkeypatch.setattr("app.api.admin.routes.AuditService", lambda: FakeAuditService())
    resp = TestClient(app).get("/api/admin/audit/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    assert "mensaje_id" in body
    assert "observaciones" in body
    assert "LLM: x [text]" in body


def test_export_comprobantes_csv(monkeypatch):
    app = _make_app(_admin())
    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: FakeBilling())
    resp = TestClient(app).get("/api/admin/comprobantes/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    assert "tipo_comprobante" in body
    assert "FACTURA" in body


def test_export_metrics_csv(monkeypatch):
    app = _make_app(_admin())
    monkeypatch.setattr("app.api.admin.routes.AdminService", lambda: FakeAdminService())
    resp = TestClient(app).get("/api/admin/metrics/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    assert "AGREGADOS" in body
    assert "TOKENS POR MODELO" in body
    assert "openai/gpt-4o-mini" in body
    assert "SERIE" in body
    assert "Reglamento" in body


def test_export_blocks_platform_admin_without_membership(monkeypatch):
    auth = AuthContext(external_auth_id="pa", institucion_id=None, tipo_miembro=None, is_platform_admin=True)
    app = _make_app(auth)
    monkeypatch.setattr("app.api.admin.routes.AuditService", lambda: FakeAuditService())
    resp = TestClient(app).get("/api/admin/audit/export")
    assert resp.status_code == 403