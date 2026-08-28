from __future__ import annotations

"""E2E de integración Stripe (Checkout, subscription) vía TestClient.
Usa dependency_overrides para saltar JWT, pero toca Stripe real y Supabase real.
Requiere: (a) plan en Supabase, (b) institución con id dado por INST_ID.
"""
from fastapi.testclient import TestClient
from app.main import create_app
from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_admin_auth
from app.core.supabase import get_supabase_client

# Ajustar según el ID devuelto por el seed (o usar 1 si ya existe institución)
INST_ID = 1  # "Universidad de Prueba A"
PLAN_ID = None  # Se debe completar tras insertar el plan en DB


def _fake_admin():
    return AuthContext(
        external_auth_id="e2e-stripe-test",
        email="test@e2e.local",
        full_name="E2E Stripe",
        institucion_id=INST_ID,
        tipo_miembro="ADMIN",
        is_platform_admin=False,
    )


app = create_app()
app.dependency_overrides[get_admin_auth] = _fake_admin

client = TestClient(app)


import pytest

@pytest.mark.integration
def test_checkout_live():
    # Primero verificar/leer el plan insertado (o usar un plan existente si se creó)
    repo = get_supabase_client()
    plan_res = repo.table("planes").select("id, stripe_price_id").eq("stripe_price_id", "price_1U9BwkHVmTPbjjVgOf7GIprr").execute()
    rows = plan_res.data or []
    if not rows:
        raise ValueError("Plan no insertado en planes (stripe_price_id=price_1U9BwkHVmTPbjjVgOf7GIprr). Ejecuta el seed SQL primero.")
    plan_id = rows[0]["id"]

    resp = client.post(
        "/api/admin/stripe/checkout",
        json={
            "plan_id": plan_id,
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("url") is not None
    assert body.get("session_id") is not None
    print("\n=== CHECKOUT URL (abrir en navegador para pagar con test card) ===")
    print(body["url"])
    print("===============================================================\n")
