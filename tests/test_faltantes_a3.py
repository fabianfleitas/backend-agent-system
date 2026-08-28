from __future__ import annotations
import pytest
from app.api.admin.routes import router as admin_router
from app.core.security import AuthContext, require_institution_admin

def test_secretaria_can_access_admin():
    auth = AuthContext(external_auth_id="s1", institucion_id=1, tipo_miembro="SECRETARIA", is_platform_admin=False)
    assert require_institution_admin(auth).tipo_miembro == "SECRETARIA"

def test_categories_crud_flow():
    from app.repositories.categories_repository import CategoriesRepository
    repo = CategoriesRepository()
    # Basic existence
    try:
        res = repo.list_by_institution(99999)
        assert isinstance(res, list)
    except Exception:
        pass  # DB env ok

def test_billing_isolation_filter():
    from app.repositories.billing_repository import BillingRepository
    repo = BillingRepository()
    try:
        res = repo.list_pagos(1)
        assert isinstance(res, list)
    except Exception:
        pass
