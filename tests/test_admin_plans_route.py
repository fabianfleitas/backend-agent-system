from __future__ import annotations

"""Tests for GET /api/admin/plans (listado de planes para change-plan)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_auth_context


def _make_app(auth: AuthContext):
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_auth_context] = lambda: auth
    return app


def _admin_auth() -> AuthContext:
    return AuthContext(
        external_auth_id="a",
        institucion_id=1,
        tipo_miembro="ADMIN",
        is_platform_admin=False,
    )


class FakeBilling:
    def __init__(self, plans):
        self._plans = plans

    def list_plans_for_admin(self):
        return [p for p in self._plans if p.get("stripe_price_id")]


def test_admin_plans_returns_synced_only(monkeypatch):
    app = _make_app(_admin_auth())
    plans = [
        {"id": 1, "codigo": "BAS", "nombre": "Base", "precio": 10, "moneda": "USD",
         "intervalo": "month", "max_documentos": 5, "max_usuarios": 10, "max_estudiantes": 50,
         "features": {}, "activo": True, "stripe_price_id": "price_1"},
        {"id": 2, "codigo": "PRO", "nombre": "Pro", "precio": 20, "moneda": "USD",
         "intervalo": "month", "max_documentos": 50, "max_usuarios": 100, "max_estudiantes": 500,
         "features": {}, "activo": True, "stripe_price_id": None},
    ]
    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: FakeBilling(plans))
    resp = TestClient(app).get("/api/admin/plans")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["stripe_price_id"] == "price_1"
    assert data[0]["nombre"] == "Base"


def test_admin_plans_blocks_platform_admin_without_membership(monkeypatch):
    auth = AuthContext(
        external_auth_id="pa",
        institucion_id=None,
        tipo_miembro=None,
        is_platform_admin=True,
    )
    app = _make_app(auth)
    monkeypatch.setattr("app.api.admin.routes.BillingService", lambda: FakeBilling([]))
    resp = TestClient(app).get("/api/admin/plans")
    assert resp.status_code == 403