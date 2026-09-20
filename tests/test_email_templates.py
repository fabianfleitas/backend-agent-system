from __future__ import annotations

"""Tests para CRUD de plantillas email (GET/POST/PUT/DELETE /api/admin/email-templates)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.email_templates_routes import router as templates_router
from app.core.security import AuthContext, get_auth_context
from app.services.email_template_service import EmailTemplateService


def _make_app(auth: AuthContext):
    app = FastAPI()
    app.include_router(templates_router, prefix="/api/admin")
    app.dependency_overrides[get_auth_context] = lambda: auth
    return app


def _admin() -> AuthContext:
    return AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN")


TEMPLATE = {
    "id": 1,
    "institucion_id": 1,
    "codigo": "WELCOME",
    "nombre": "Bienvenida",
    "asunto": "Bienvenido",
    "contenido_html": "<p>Hola</p>",
    "contenido_texto": "Hola",
    "activo": True,
    "created_at": "2026-01-01T00:00:00Z",
}


class FakeTemplateService:
    def __init__(self):
        self.calls = []

    def list(self, auth):
        self.calls.append("list")
        return [dict(TEMPLATE)]

    def create(self, auth, payload):
        self.calls.append(("create", payload.codigo))
        return dict(TEMPLATE, codigo=payload.codigo)

    def update(self, auth, template_id, payload):
        self.calls.append(("update", template_id))
        return dict(TEMPLATE, nombre=payload.nombre) if template_id == 1 else None

    def deactivate(self, auth, template_id):
        self.calls.append(("deactivate", template_id))
        return dict(TEMPLATE) if template_id == 1 else None


def _apply_fake(monkeypatch, svc):
    monkeypatch.setattr("app.api.admin.email_templates_routes.EmailTemplateService", lambda: svc)


def test_list_templates(monkeypatch):
    svc = FakeTemplateService()
    _apply_fake(monkeypatch, svc)
    app = _make_app(_admin())
    resp = TestClient(app).get("/api/admin/email-templates")
    assert resp.status_code == 200
    assert resp.json()[0]["codigo"] == "WELCOME"


def test_create_template(monkeypatch):
    svc = FakeTemplateService()
    _apply_fake(monkeypatch, svc)
    app = _make_app(_admin())
    resp = TestClient(app).post(
        "/api/admin/email-templates",
        json={"codigo": "PAYMENT", "nombre": "Pago", "asunto": "Pago recibido", "contenido_html": "<p>x</p>"},
    )
    assert resp.status_code == 201
    assert resp.json()["codigo"] == "PAYMENT"
    assert svc.calls[0][0] == "create"


def test_update_template(monkeypatch):
    svc = FakeTemplateService()
    _apply_fake(monkeypatch, svc)
    app = _make_app(_admin())
    resp = TestClient(app).put(
        "/api/admin/email-templates/1",
        json={"codigo": "WELCOME", "nombre": "Renombrada", "asunto": "Bienvenido", "activo": True},
    )
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Renombrada"
    assert TestClient(app).put(
        "/api/admin/email-templates/99",
        json={"codigo": "X", "nombre": "X", "asunto": "X"},
    ).status_code == 404


def test_deactivate_template(monkeypatch):
    svc = FakeTemplateService()
    _apply_fake(monkeypatch, svc)
    app = _make_app(_admin())
    assert TestClient(app).delete("/api/admin/email-templates/1").status_code == 204
    assert TestClient(app).delete("/api/admin/email-templates/99").status_code == 404


def test_templates_blocks_platform_admin_without_membership(monkeypatch):
    auth = AuthContext(external_auth_id="pa", institucion_id=None, tipo_miembro=None, is_platform_admin=True)
    svc = FakeTemplateService()
    _apply_fake(monkeypatch, svc)
    app = _make_app(auth)
    assert TestClient(app).get("/api/admin/email-templates").status_code == 403
    assert TestClient(app).post("/api/admin/email-templates", json={"codigo": "X", "nombre": "X", "asunto": "X"}).status_code == 403


# --- Service level ---

class FakeRepo:
    def __init__(self):
        self.created = None
        self.updated = None

    def list_global(self):
        return [dict(TEMPLATE, institucion_id=None)]

    def list_by_institution(self, institucion_id):
        return [dict(TEMPLATE)]

    def create(self, **kw):
        self.created = kw
        return {"id": 5, **kw}

    def update(self, template_id, **kw):
        self.updated = (template_id, kw)
        return {"id": template_id, **kw}

    def deactivate(self, template_id):
        return {"id": template_id, "activo": False}

    def get_by_id(self, template_id):
        return {"id": template_id, "institucion_id": 1, "activo": True}


def _payload():
    class P:
        codigo = "A"
        nombre = "N"
        asunto = "S"
        contenido_html = "<p>x</p>"
        contenido_texto = None
        activo = True
    return P()


def test_service_scope_institutional_vs_global():
    repo = FakeRepo()
    svc = EmailTemplateService(repository=repo)
    inst = AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN")
    assert svc.list(inst) == [dict(TEMPLATE)]
    assert svc.list(AuthContext(external_auth_id="pa", institucion_id=None, tipo_miembro=None, is_platform_admin=True)) == [dict(TEMPLATE, institucion_id=None)]
    svc.create(inst, _payload())
    assert repo.created["institucion_id"] == 1


def test_service_ownership_prevents_cross_institution():
    repo = FakeRepo()
    svc = EmailTemplateService(repository=repo)
    other = AuthContext(external_auth_id="b", institucion_id=2, tipo_miembro="ADMIN")
    assert svc.update(other, 1, _payload()) is None
    assert svc.deactivate(other, 1) is None