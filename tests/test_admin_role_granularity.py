from __future__ import annotations

"""S8 — Granularidad de rol ADMIN vs SECRETARIA en /api/admin/*.

Los endpoints reservados (billing, configuración, usuarios y moderación de
feedback) requieren rol ADMIN; SECRETARIA recibe 403. Los endpoints operativos
(documentos, categorías, auditoría, métricas, conversaciones) aceptan staff.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, get_auth_context

SECRETARIA = AuthContext(
    external_auth_id="sec1",
    institucion_id=1,
    tipo_miembro="SECRETARIA",
    is_platform_admin=False,
)
ADMIN = AuthContext(
    external_auth_id="adm1",
    institucion_id=1,
    tipo_miembro="ADMIN",
    is_platform_admin=False,
)


def _app(auth: AuthContext):
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    app.dependency_overrides[get_auth_context] = lambda: auth
    return app


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/admin/users"),
    ("GET", "/api/admin/feedback"),
    ("GET", "/api/admin/config"),
    ("GET", "/api/admin/subscription"),
    ("GET", "/api/admin/subscription/history"),
    ("GET", "/api/admin/plan"),
    ("GET", "/api/admin/plans"),
    ("GET", "/api/admin/pagos"),
    ("GET", "/api/admin/comprobantes"),
    ("GET", "/api/admin/stripe/subscription"),
])
def test_secretaria_blocked_on_admin_only_endpoints(method, path):
    app = _app(SECRETARIA)
    resp = TestClient(app).request(method, path)
    assert resp.status_code == 403
    assert "Administrator access required" in resp.json().get("detail", "")


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/admin/documents"),
    ("GET", "/api/admin/audit"),
    ("GET", "/api/admin/metrics"),
    ("GET", "/api/admin/conversations"),
    ("GET", "/api/admin/escalamientos"),
])
def test_secretaria_allowed_on_staff_endpoints(method, path):
    app = _app(SECRETARIA)
    resp = TestClient(app).request(method, path)
    # El guard deja pasar (cualquier status posterior depende de fakes/DB)
    assert resp.status_code != 403


def test_admin_allowed_past_guard():
    app = _app(ADMIN)
    resp = TestClient(app).get("/api/admin/config")
    # 200 si el service/repo real responde; el punto es que NO sea 403 por rol
    assert resp.status_code != 403