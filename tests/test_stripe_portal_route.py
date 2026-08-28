from __future__ import annotations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_admin_auth

def _make_app():
    app = FastAPI(); app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_admin_auth] = lambda: AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False)
    return app

def test_portal_session(monkeypatch):
    app = _make_app()
    class FakeSvc:
        def create_billing_portal_session(self, auth, return_url):
            return {"url": "https://billing.stripe.com/session/portal_123", "id": "portal_123", "customer": "cus_1"}
    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: FakeSvc())
    resp = TestClient(app).post("/api/admin/stripe/portal-session", json={"return_url":"https://example.com/return"})
    assert resp.status_code == 200
    assert resp.json()["url"].startswith("https://")
