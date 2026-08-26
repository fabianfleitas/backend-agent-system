from __future__ import annotations

from app.core.security import AuthContext, require_institution_admin
from fastapi import HTTPException

def test_platform_admin_without_membership_blocked_for_admin():
    auth = AuthContext(external_auth_id="p1", is_platform_admin=True, institucion_id=None, tipo_miembro=None)
    try:
        require_institution_admin(auth)
        assert False, "Debe rechazar platform admin sin membresía"
    except HTTPException as e:
        assert e.status_code == 403

def test_admin_with_membership_ok():
    auth = AuthContext(external_auth_id="a1", institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False)
    result = require_institution_admin(auth)
    assert result.institucion_id == 1
