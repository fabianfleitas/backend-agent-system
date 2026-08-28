from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_admin_auth


class _FakeStripeService:
    configured = True

    def create_or_update_product(self, **kwargs):
        return {"id": "prod_123"}

    def create_or_update_price(self, **kwargs):
        return {"id": "price_123"}


class _FakePlanRepo:
    def get_plan(self, plan_id: int):
        return {
            "id": plan_id,
            "nombre": "Plan Pro",
            "descripcion": "Plan institucional",
            "precio": 12.5,
            "moneda": "USD",
            "intervalo": "monthly",
            "activo": True,
            "codigo": "pro",
            "stripe_product_id": None,
            "stripe_price_id": None,
        }

    def update_plan_stripe_refs(self, plan_id: int, *, stripe_product_id=None, stripe_price_id=None):
        return {
            "stripe_product_id": stripe_product_id,
            "stripe_price_id": stripe_price_id,
        }


class _FakeBillingService:
    def __init__(self) -> None:
        self.repo = _FakePlanRepo()


def test_sync_plan_with_stripe(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_admin_auth] = lambda: AuthContext(
        external_auth_id="admin-1",
        institucion_id=1,
        tipo_miembro="ADMIN",
        is_platform_admin=False,
        auth_provider="supabase",
    )

    monkeypatch.setattr("app.api.admin.routes.get_stripe_agent_service", lambda: _FakeStripeService())
    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: _FakeBillingService())

    client = TestClient(app)
    resp = client.post("/api/admin/stripe/sync-plan", json={"plan_id": 7})
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan_id"] == 7
    assert body["stripe_product_id"] == "prod_123"
    assert body["stripe_price_id"] == "price_123"
    assert body["stripe_product_created"] is True
    assert body["stripe_price_created"] is True
