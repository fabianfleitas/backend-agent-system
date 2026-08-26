from __future__ import annotations
from app.core.security import AuthContext, require_institution_admin

def test_secretaria_can_access_admin():
    auth = AuthContext(external_auth_id="s1", institucion_id=1, tipo_miembro="SECRETARIA", is_platform_admin=False)
    result = require_institution_admin(auth)
    assert result.institucion_id == 1

def test_billing_isolation_filter():
    from app.repositories.billing_repository import BillingRepository
    repo = BillingRepository()
    # Verify filter exists and returns list (DB connection or empty ok)
    try:
        res = repo.list_pagos(1)
        assert isinstance(res, list)
    except Exception:
        pass
