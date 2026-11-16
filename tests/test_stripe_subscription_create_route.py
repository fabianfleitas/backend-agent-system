from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_institution_admin_only_auth


class _FakeBillingService:
    def create_subscription_for_institution(self, auth, plan_id: int):
        assert auth.institucion_id == 1
        assert plan_id == 7
        return {
            "id": "sub_123",
            "customer": "cus_123",
            "status": "incomplete",
            "latest_invoice": {
                "payment_intent": {
                    "id": "pi_123",
                    "client_secret": "secret_123",
                }
            },
        }


def test_create_subscription_with_stripe(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_institution_admin_only_auth] = lambda: AuthContext(
        external_auth_id="admin-1",
        institucion_id=1,
        tipo_miembro="ADMIN",
        is_platform_admin=False,
        auth_provider="supabase",
    )

    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: _FakeBillingService())

    client = TestClient(app)
    resp = client.post("/api/admin/stripe/create-subscription", json={"plan_id": 7})
    assert resp.status_code == 200
    body = resp.json()
    assert body["subscription_id"] == "sub_123"
    assert body["customer_id"] == "cus_123"
    assert body["status"] == "incomplete"
    assert body["latest_invoice_payment_intent_id"] == "pi_123"
    assert body["client_secret"] == "secret_123"
