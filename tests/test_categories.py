from __future__ import annotations

import pytest

from app.core.security import AuthContext
from app.services.categories_service import CategoriesService
from app.repositories.categories_repository import CategoriesRepository


class FakeCategoriesRepository:
    def __init__(self, cats_by_inst: dict = None) -> None:
        self.cats_by_inst = cats_by_inst or {}

    def list_by_institution(self, institucion_id: int) -> list[dict]:
        return self.cats_by_inst.get(institucion_id, [])

    def get_by_id(self, categoria_id: int, institucion_id: int) -> dict | None:
        for c in self.cats_by_inst.get(institucion_id, []):
            if c["id"] == categoria_id:
                return c
        return None


def make_auth(institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False) -> AuthContext:
    return AuthContext(
        external_auth_id=f"admin-{institucion_id}",
        institucion_id=institucion_id,
        tipo_miembro=tipo_miembro,
        is_platform_admin=is_platform_admin,
    )


def test_list_by_institution_filters_by_id() -> None:
    repo = FakeCategoriesRepository({
        1: [{"id": 1, "nombre": "Matriculación", "institucion_id": 1, "activo": True, "fecha_creacion": "2026-01-01T00:00:00Z", "descripcion": ""}],
        2: [{"id": 10, "nombre": "Becas", "institucion_id": 2, "activo": True, "fecha_creacion": "2026-01-01T00:00:00Z", "descripcion": ""}],
    })
    svc = CategoriesService(repository=repo)
    result = svc.list_by_institution(make_auth(institucion_id=1))
    assert len(result) == 1
    assert result[0]["nombre"] == "Matriculación"


def test_list_by_institution_no_membership_empty() -> None:
    repo = FakeCategoriesRepository({1: [{"id": 1, "nombre": "X", "institucion_id": 1, "activo": True, "fecha_creacion": "2026-01-01", "descripcion": ""}]})
    svc = CategoriesService(repository=repo)
    result = svc.list_by_institution(make_auth(institucion_id=None))
    assert result == []


def test_get_by_id_same_institution_found() -> None:
    repo = FakeCategoriesRepository({1: [{"id": 3, "nombre": "Aranceles", "institucion_id": 1, "activo": True, "fecha_creacion": "2026-01-01", "descripcion": ""}]})
    svc = CategoriesService(repository=repo)
    result = svc.get_by_id(3, make_auth(institucion_id=1))
    assert result is not None
    assert result["nombre"] == "Aranceles"


def test_get_by_id_different_institution_none() -> None:
    repo = FakeCategoriesRepository({2: [{"id": 3, "nombre": "Aranceles", "institucion_id": 2, "activo": True, "fecha_creacion": "2026-01-01", "descripcion": ""}]})
    svc = CategoriesService(repository=repo)
    result = svc.get_by_id(3, make_auth(institucion_id=1))
    assert result is None
