from __future__ import annotations

"""C4 — CRUD de instituciones y planes en /api/platform/* (platform admin)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.platform.routes import router as platform_router, _get_plat_service
from app.core.security import AuthContext, get_auth_context
from app.services.platform_service import PlatformService


def _make_app(auth: AuthContext, fake_service):
    app = FastAPI()
    app.include_router(platform_router, prefix="/api/platform")
    app.dependency_overrides[get_auth_context] = lambda: auth
    app.dependency_overrides[_get_plat_service] = lambda: fake_service
    return app


def _platform_auth() -> AuthContext:
    return AuthContext(external_auth_id="pa", institucion_id=None, tipo_miembro=None, is_platform_admin=True)


def _institution_admin() -> AuthContext:
    return AuthContext(external_auth_id="ia", institucion_id=1, tipo_miembro="ADMIN")


INSTITUTION = {
    "id": 1, "codigo": "UNI", "nombre": "Universidad X", "nombre_comercial": "UNI",
    "ciudad": "Lima", "pais": "PE", "direccion": None, "email_contacto": "a@uni.pe",
    "telefono_contacto": None, "activo": True, "stripe_customer_id": None,
    "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
}

PLAN = {
    "id": 1, "codigo": "BAS", "nombre": "Base", "descripcion": None, "precio": 10.0,
    "moneda": "USD", "intervalo": "month", "max_documentos": 5, "max_usuarios": 10,
    "max_estudiantes": 50, "features": None, "activo": True, "stripe_product_id": None,
    "stripe_price_id": None, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
}


class FakePlatformService:
    def __init__(self):
        self.calls = []

    def create_institution(self, **campos):
        self.calls.append(("create_institution", campos))
        return dict(INSTITUTION, **campos)

    def update_institution(self, institucion_id, **campos):
        self.calls.append(("update_institution", institucion_id, campos))
        return dict(INSTITUTION, **campos) if institucion_id == 1 else None

    def deactivate_institution(self, institucion_id):
        self.calls.append(("deactivate_institution", institucion_id))
        return dict(INSTITUTION) if institucion_id == 1 else None

    def create_plan(self, **campos):
        self.calls.append(("create_plan", campos))
        return dict(PLAN, **campos)

    def update_plan(self, plan_id, **campos):
        self.calls.append(("update_plan", plan_id, campos))
        return dict(PLAN, **campos) if plan_id == 1 else None

    def deactivate_plan(self, plan_id):
        self.calls.append(("deactivate_plan", plan_id))
        return dict(PLAN) if plan_id == 1 else None


# --- Guards: solo platform admin ---

def test_platform_crud_blocks_institutional_admin():
    app = _make_app(_institution_admin(), FakePlatformService())
    client = TestClient(app)
    assert client.post("/api/platform/institutions", json={"nombre": "X"}).status_code == 403
    assert client.put("/api/platform/institutions/1", json={"nombre": "X"}).status_code == 403
    assert client.delete("/api/platform/institutions/1").status_code == 403
    assert client.post("/api/platform/plans", json={"nombre": "X"}).status_code == 403
    assert client.put("/api/platform/plans/1", json={"nombre": "X"}).status_code == 403
    assert client.delete("/api/platform/plans/1").status_code == 403


# --- Institutions CRUD ---

def test_create_institution(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    resp = TestClient(app).post("/api/platform/institutions", json={"codigo": "U2", "nombre": "U2", "pais": "PE"})
    assert resp.status_code == 201
    assert resp.json()["nombre"] == "U2"
    assert svc.calls[0][0] == "create_institution"


def test_update_institution(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    resp = TestClient(app).put("/api/platform/institutions/1", json={"nombre": "Renombrada"})
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Renombrada"


def test_update_institution_404(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    resp = TestClient(app).put("/api/platform/institutions/99", json={"nombre": "X"})
    assert resp.status_code == 404


def test_deactivate_institution(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    assert TestClient(app).delete("/api/platform/institutions/1").status_code == 204
    assert TestClient(app).delete("/api/platform/institutions/99").status_code == 404


# --- Plans CRUD ---

def test_create_plan(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    resp = TestClient(app).post("/api/platform/plans", json={"codigo": "PRO", "nombre": "Pro", "precio": 20})
    assert resp.status_code == 201
    assert resp.json()["nombre"] == "Pro"
    assert svc.calls[0][0] == "create_plan"


def test_update_plan(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    resp = TestClient(app).put("/api/platform/plans/1", json={"nombre": "Pro Plus"})
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Pro Plus"
    assert TestClient(app).put("/api/platform/plans/99", json={"nombre": "X"}).status_code == 404


def test_deactivate_plan(monkeypatch):
    svc = FakePlatformService()
    app = _make_app(_platform_auth(), svc)
    assert TestClient(app).delete("/api/platform/plans/1").status_code == 204
    assert TestClient(app).delete("/api/platform/plans/99").status_code == 404


# --- Service level ---

def test_platform_service_deactivates_soft(monkeypatch):
    class FakeInstRepo:
        def __init__(self):
            self.updated = None

        def deactivate_institucion(self, institucion_id):
            self.updated = institucion_id
            return {"id": institucion_id, "activo": False}

    class FakeBilling:
        def __init__(self):
            self.updated = None

        def deactivate_plan(self, plan_id):
            self.updated = plan_id
            return {"id": plan_id, "activo": False}

    inst = FakeInstRepo()
    bill = FakeBilling()
    svc = PlatformService(
        institutions_repo=inst,
        audit_repo=object(),
        admin_service=object(),
        billing_repo=bill,
    )
    svc.deactivate_institution(7)
    svc.deactivate_plan(3)
    assert inst.updated == 7
    assert bill.updated == 3