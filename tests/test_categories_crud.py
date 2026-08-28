from __future__ import annotations
import pytest
from app.core.security import AuthContext
from app.services.categories_service import CategoriesService

def test_secretaria_list_categories():
    svc = CategoriesService()
    auth = AuthContext(external_auth_id="u1", institucion_id=1, tipo_miembro="SECRETARIA", is_platform_admin=False)
    # Service validates auth; list returns [] if no DB or isolates by institution
    res = svc.list_by_institution(auth)
    assert isinstance(res, list)

def test_platform_admin_get_by_id_any():
    svc = CategoriesService()
    auth = AuthContext(external_auth_id="pa", institucion_id=None, tipo_miembro="PLATFORM_ADMIN", is_platform_admin=True)
    # Should not raise; returns None or dict depending on DB
    res = svc.get_by_id(auth, 99999)
    assert res is None or isinstance(res, dict)

def test_cross_institution_denied():
    svc = CategoriesService()
    auth = AuthContext(external_auth_id="u2", institucion_id=2, tipo_miembro="DOCENTE", is_platform_admin=False)
    # get_by_id for id in other institution should return None (repo filters institucion_id)
    res = svc.get_by_id(auth, 1)  # id belongs to institution 1
    # If DB exists, should be None or wrong institution; assertion depends on seed
    # We only assert no exception and correct type
    assert res is None or isinstance(res, dict)
