from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_admin_auth


class _FakeBillingService:
    def cancel_subscription_for_institution(self, auth, cancel_at_period_end: bool = True):
        assert auth.institucion_id == 1
        assert cancel_at_period_end is True
        return {
            "id": "sub_123",
            "customer": "cus_123",
            "status": "active",
            "cancel_at_period_end": True,
            "canceled_at": None,
        }

    def reactivate_subscription_for_institution(self, auth):
        assert auth.institucion_id == 1
        return {
            "id": "sub_123",
            "customer": "cus_123",
            "status": "active",
            "cancel_at_period_end": False,
            "canceled_at": None,
        }


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_admin_auth] = lambda: AuthContext(
        external_auth_id="admin-1",
        institucion_id=1,
        tipo_miembro="ADMIN",
        is_platform_admin=False,
        auth_provider="supabase",
    )
    return app


def test_cancel_subscription_with_stripe(monkeypatch) -> None:
    app = _make_app()
    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: _FakeBillingService())

    client = TestClient(app)
    resp = client.post("/api/admin/stripe/cancel-subscription", json={"cancel_at_period_end": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["subscription_id"] == "sub_123"
    assert body["customer_id"] == "cus_123"
    assert body["status"] == "active"
    assert body["cancel_at_period_end"] is True


def test_reactivate_subscription_with_stripe(monkeypatch) -> None:
    app = _make_app()
    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: _FakeBillingService())

    client = TestClient(app)
    resp = client.post("/api/admin/stripe/reactivate-subscription")
    assert resp.status_code == 200
    body = resp.json()
    assert body["subscription_id"] == "sub_123"
    assert body["customer_id"] == "cus_123"
    assert body["status"] == "active"
    assert body["cancel_at_period_end"] is False
