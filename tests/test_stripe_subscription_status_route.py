from __future__ import annotations
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_admin_auth

class _FakeStripeAgent:
    configured = True
    def retrieve_subscription(self, sid):
        return {"id": sid, "customer": "cus_1", "status": "active", "cancel_at_period_end": False, "current_period_end": "2026-09-01", "current_period_start": "2026-08-01", "latest_invoice": {"payment_intent": {"id": "pi_1"}}}

def test_get_stripe_subscription(monkeypatch):
    app = FastAPI(); app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_admin_auth] = lambda: AuthContext(external_auth_id="a1", institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False)
    monkeypatch.setattr("app.api.admin.routes.get_stripe_agent_service", lambda: _FakeStripeAgent())
    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: type("S",(),{"get_stripe_subscription":lambda self,auth:{"id":"sub_1","customer":"cus_1","status":"active","cancel_at_period_end":False,"current_period_end":"2026-09-01","current_period_start":"2026-08-01","latest_invoice":{"payment_intent":{"id":"pi_1"}}}})())
    client = TestClient(app)
    resp = client.get("/api/admin/stripe/subscription")
    assert resp.status_code == 200
    assert resp.json()["subscription_id"] == "sub_1"
