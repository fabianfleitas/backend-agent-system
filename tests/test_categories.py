from __future__ import annotations

from app.core.security import AuthContext
from app.services.categories_service import CategoriesService
from app.repositories.categories_repository import CategoriesRepository


class FakeCategoriesRepository:
    def __init__(self, cats_by_inst: dict = None, globals: list = None, by_id_map: dict = None) -> None:
        self.cats_by_inst = cats_by_inst or {}
        self.global_cats = globals or []
        self.by_id_map = by_id_map or {}

    def list_by_institution(self, institucion_id: int) -> list[dict]:
        return self.cats_by_inst.get(institucion_id, [])

    def list_global(self) -> list[dict]:
        return list(self.global_cats)

    def list_by_institution_and_global(self, institucion_id: int) -> list[dict]:
        by_key: dict[str, dict] = {}
        for c in self.list_global():
            by_key[str(c.get("nombre", "")).strip().lower()] = c
        for c in self.list_by_institution(institucion_id):
            by_key[str(c.get("nombre", "")).strip().lower()] = c
        return list(by_key.values())

    def get_by_id(self, categoria_id: int, institucion_id: int) -> dict | None:
        for c in self.cats_by_inst.get(institucion_id, []):
            if c["id"] == categoria_id:
                return c
        return None

    def get_by_id_with_global(self, categoria_id: int, institucion_id: int) -> dict | None:
        return self.get_by_id(categoria_id, institucion_id) or next(
            (c for c in self.global_cats if c["id"] == categoria_id), None
        )

    def get_by_id_any(self, categoria_id: int) -> dict | None:
        return self.by_id_map.get(categoria_id)


def make_auth(institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False) -> AuthContext:
    return AuthContext(
        external_auth_id=f"admin-{institucion_id}",
        institucion_id=institucion_id,
        tipo_miembro=tipo_miembro,
        is_platform_admin=is_platform_admin,
    )


INST_CAT = {
    "id": 1,
    "nombre": "Matriculación",
    "institucion_id": 1,
    "activo": True,
    "fecha_creacion": "2026-01-01T00:00:00Z",
    "descripcion": "",
}


def test_list_by_institution_filters_by_id() -> None:
    repo = FakeCategoriesRepository({
        1: [INST_CAT],
        2: [{"id": 10, "nombre": "Becas", "institucion_id": 2, "activo": True, "fecha_creacion": "2026-01-01T00:00:00Z", "descripcion": ""}],
    })
    svc = CategoriesService(repository=repo)
    result = svc.list_by_institution(make_auth(institucion_id=1))
    assert len(result) == 1
    assert result[0]["nombre"] == "Matriculación"


def test_list_by_institution_no_membership_empty() -> None:
    repo = FakeCategoriesRepository({1: [INST_CAT]})
    svc = CategoriesService(repository=repo)
    result = svc.list_by_institution(make_auth(institucion_id=None))
    assert result == []


def test_list_merges_global_and_institutional_with_institutional_precedence() -> None:
    repo = FakeCategoriesRepository(
        cats_by_inst={
            1: [{"id": 2, "nombre": "Reglamentos", "institucion_id": 1, "activo": True, "fecha_creacion": "2026-01-01", "descripcion": ""}],
        },
        globals=[
            {"id": 100, "nombre": "General", "institucion_id": None, "activo": True, "fecha_creacion": "2026-01-01", "descripcion": ""},
            {"id": 200, "nombre": "reglamentos", "institucion_id": None, "activo": True, "fecha_creacion": "2026-01-01", "descripcion": ""},
        ],
    )
    svc = CategoriesService(repository=repo)
    result = svc.list_by_institution(make_auth(institucion_id=1))
    names = {c["nombre"] for c in result}
    assert names == {"General", "Reglamentos"}
    reglamentos = next(c for c in result if c["nombre"] == "Reglamentos")
    assert reglamentos["id"] == 2  # la institucional prevalece sobre la global (200)


def test_list_platform_admin_returns_globals_only() -> None:
    repo = FakeCategoriesRepository(
        cats_by_inst={1: [INST_CAT]},
        globals=[{"id": 100, "nombre": "General", "institucion_id": None, "activo": True, "fecha_creacion": "2026-01-01", "descripcion": ""}],
    )
    svc = CategoriesService(repository=repo)
    result = svc.list_by_institution(make_auth(institucion_id=None, is_platform_admin=True))
    assert [c["id"] for c in result] == [100]


def test_get_by_id_same_institution_found() -> None:
    repo = FakeCategoriesRepository({1: [{"id": 3, "nombre": "Aranceles", "institucion_id": 1, "activo": True, "fecha_creacion": "2026-01-01", "descripcion": ""}]})
    svc = CategoriesService(repository=repo)
    result = svc.get_by_id(make_auth(institucion_id=1), 3)
    assert result is not None
    assert result["nombre"] == "Aranceles"


def test_get_by_id_different_institution_falls_back_to_global() -> None:
    repo = FakeCategoriesRepository(
        cats_by_inst={2: [{"id": 3, "nombre": "Aranceles", "institucion_id": 2, "activo": True, "fecha_creacion": "2026-01-01", "descripcion": ""}]},
        globals=[{"id": 400, "nombre": "Pagaduría", "institucion_id": None, "activo": True, "fecha_creacion": "2026-01-01", "descripcion": ""}],
    )
    svc = CategoriesService(repository=repo)
    result = svc.get_by_id(make_auth(institucion_id=1), 400)
    assert result is not None
    assert result["nombre"] == "Pagaduría"


def test_get_by_id_unknown_returns_none() -> None:
    repo = FakeCategoriesRepository(cats_by_inst={1: [INST_CAT]}, globals=[])
    svc = CategoriesService(repository=repo)
    assert svc.get_by_id(make_auth(institucion_id=1), 999) is None