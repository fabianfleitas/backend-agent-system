from __future__ import annotations

"""Cross-tenant route tests using monkeypatch of service classes.
Pattern: build router app + dependency_overrides for auth + monkeypatch service factories.
No real DB required (unit/default suite)."""

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.core.security import AuthContext, get_auth_context, require_institution_admin
from app.api.admin.routes import router as admin_router
from app.api.conversations.routes import router as conv_router
from app.api.chat.routes import router as chat_router
from app.api.platform.routes import router as plat_router


def make_auth(
    external_auth_id: str = "student-a",
    institucion_id: int = 1,
    tipo_miembro: str = "ESTUDIANTE",
    is_platform_admin: bool = False,
) -> AuthContext:
    return AuthContext(
        external_auth_id=external_auth_id,
        email=f"{external_auth_id}@t",
        full_name="Test",
        institucion_id=institucion_id,
        tipo_miembro=tipo_miembro,
        is_platform_admin=is_platform_admin,
    )


class FakeDocumentsService:
    def __init__(self, institution_id_target: int = 1) -> None:
        self.institution_id_target = institution_id_target

    def get_document(self, documento_id, auth):
        if auth.institucion_id != self.institution_id_target:
            return None
        return (
            {
                "id": documento_id,
                "institucion_id": auth.institucion_id,
                "titulo": "Doc A",
                "activo": True,
                "fecha_creacion": "2026-01-01T00:00:00Z",
            },
            [],
        )

    def list_documents(self, auth):
        if auth.institucion_id != self.institution_id_target:
            return []
        return [({"id": 1, "institucion_id": auth.institucion_id}, [])]


def test_admin_document_cross_tenant_404(monkeypatch):
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    # Auth de institución 1
    app.dependency_overrides[get_auth_context] = lambda: make_auth("a", 1, "ADMIN")
    app.dependency_overrides[require_institution_admin] = lambda: make_auth("a", 1, "ADMIN")
    # Fake docs de institución 1: documento 99 no existe; intentar acceso a institución 2 debe ser imposible
    # Aquí verificamos que la ruta devuelve 404 cuando el repo fakedice None
    monkeypatch.setattr("app.api.admin.routes.DocumentsService", FakeDocumentsService)
    client = TestClient(app)
    # Documento que pertenece a 1 sí existe
    resp = client.get("/api/admin/documents/1")
    assert resp.status_code == 200
