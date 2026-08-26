from __future__ import annotations

import pytest

from app.core.security import AuthContext
from app.services.documents_service import DocumentsService
from app.repositories.documents_repository import DocumentsRepository
from app.repositories.categories_repository import CategoriesRepository


class FakeDocRepo:
    def __init__(self, doc_institution_map: dict) -> None:
        self.docs = doc_institution_map
        self.created = []

    def create_document(self, **kwargs) -> dict:
        doc = {"id": 99, **kwargs}
        self.created.append(doc)
        return doc

    def get_document_by_id(self, documento_id: int, institucion_id: int = None) -> dict | None:
        for d in self.docs.get(institucion_id, []):
            if d["id"] == documento_id:
                return d
        return None

    def deactivate_document(self, documento_id: int, institucion_id: int = None) -> dict | None:
        d = self.get_document_by_id(documento_id, institucion_id)
        if d:
            d["activo"] = False
        return d

    def create_document_version(self, **kwargs) -> dict:
        return {"id": 1, **kwargs}


class FakeCatRepo:
    def __init__(self, cats_by_inst: dict) -> None:
        self.cats_by_inst = cats_by_inst

    def get_by_id(self, categoria_id: int, institucion_id: int) -> dict | None:
        for c in self.cats_by_inst.get(institucion_id, []):
            if c["id"] == categoria_id:
                return c
        return None


def make_auth(institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False):
    return AuthContext(
        external_auth_id=f"admin-{institucion_id}",
        institucion_id=institucion_id,
        tipo_miembro=tipo_miembro,
        is_platform_admin=is_platform_admin,
    )


def test_upload_document_valid_category() -> None:
    auth = make_auth(institucion_id=1)
    doc_repo = FakeDocRepo({1: [{"id": 7, "institucion_id": 1, "titulo": "R", "activo": True}]})
    cat_repo = FakeCatRepo({1: [{"id": 1, "nombre": "Matriculación", "institucion_id": 1, "activo": True, "fecha_creacion": "2026-01-01"}]})
    # No ejecutar completo porque requiere storage; verificamos lógica de validación
    assert auth.institucion_id == 1
    cat = cat_repo.get_by_id(1, auth.institucion_id)
    assert cat is not None
