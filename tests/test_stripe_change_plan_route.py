from __future__ import annotations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_institution_admin_only_auth

def _make_app():
    app = FastAPI(); app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_institution_admin_only_auth] = lambda: AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False)
    return app

def test_change_plan(monkeypatch):
    app = _make_app()
    class FakeSvc:
        def change_subscription_plan(self, auth, plan_id):
            return {"id":"sub_1","customer":"cus_1","status":"active","latest_invoice":{"payment_intent":{"id":"pi_2","client_secret":"cs_2"}}}
    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: FakeSvc())
    resp = TestClient(app).post("/api/admin/stripe/change-plan", json={"plan_id":7})
    assert resp.status_code == 200
    assert resp.json()["subscription_id"] == "sub_1"
