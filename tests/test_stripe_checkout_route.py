from __future__ import annotations
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_institution_admin_only_auth

class _FakeSvc:
    configured = True
    def create_checkout_session(self, **kw):
        return {"url":"https://checkout.stripe.com/session/cs_1","id":"cs_1"}

def test_checkout_session(monkeypatch):
    app = FastAPI(); app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_institution_admin_only_auth] = lambda: AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False)
    monkeypatch.setattr("app.api.admin.routes.get_stripe_agent_service", lambda: _FakeSvc())
    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: type("S",(),{"create_checkout_session_for_institution":lambda s,a,p,su,cu: {"url":"https://checkout.stripe.com/session/cs_1","id":"cs_1"}})())
    resp = TestClient(app).post("/api/admin/stripe/checkout", json={"plan_id":7,"success_url":"https://example.com/success","cancel_url":"https://example.com/cancel"})
    assert resp.status_code == 200
    assert resp.json()["url"].startswith("https://")
