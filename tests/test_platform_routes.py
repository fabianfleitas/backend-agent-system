from __future__ import annotations

from fastapi import HTTPException
from app.core.security import AuthContext, require_platform_admin


def test_require_platform_admin_ok():
    auth = AuthContext(external_auth_id="p", is_platform_admin=True)
    assert require_platform_admin(auth) == auth


def test_platform_admin_blocked_for_admin():
    # Institutional admin sin platform admin debe fallar en /platform
    auth = AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False)
    try:
        require_platform_admin(auth)
        assert False
    except HTTPException as e:
        assert e.status_code == 403
