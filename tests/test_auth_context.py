from __future__ import annotations

from unittest.mock import patch, MagicMock

from fastapi import HTTPException
import pytest

from app.core.security import (
    AuthContext,
    get_auth_context,
    require_member,
    require_institution_admin,
    require_platform_admin,
)


def _auth_context(external_auth_id="student-1", institucion_id=1, tipo_miembro="ESTUDIANTE", is_platform_admin=False):
    return AuthContext(
        external_auth_id=external_auth_id,
        institucion_id=institucion_id,
        tipo_miembro=tipo_miembro,
        is_platform_admin=is_platform_admin,
    )


def test_require_member_without_membership_raises_403():
    auth = _auth_context(institucion_id=None, tipo_miembro=None)
    with pytest.raises(HTTPException) as exc:
        require_member(auth)
    assert exc.value.status_code == 403


def test_require_member_with_membership_passes():
    auth = _auth_context(institucion_id=1, tipo_miembro="ESTUDIANTE")
    assert require_member(auth) == auth


def test_require_member_platform_admin_bypass():
    auth = _auth_context(is_platform_admin=True)
    assert require_member(auth) == auth


def test_require_institution_admin_student_raises_403():
    auth = _auth_context(institucion_id=1, tipo_miembro="ESTUDIANTE")
    with pytest.raises(HTTPException) as exc:
        require_institution_admin(auth)
    assert exc.value.status_code == 403


def test_require_institution_admin_admin_passes():
    auth = _auth_context(institucion_id=1, tipo_miembro="ADMIN")
    assert require_institution_admin(auth) == auth


def test_require_institution_admin_secretaria_passes():
    auth = _auth_context(institucion_id=1, tipo_miembro="SECRETARIA")
    assert require_institution_admin(auth) == auth


def test_require_institution_admin_platform_admin_bypass_blocked():
    # Platform admin sin membresía NO debe pasar /admin/* (solo /platform/*)
    auth = _auth_context(is_platform_admin=True, institucion_id=None)
    with pytest.raises(HTTPException) as exc:
        require_institution_admin(auth)
    assert exc.value.status_code == 403


def test_require_platform_admin_without_raises_403():
    auth = _auth_context(is_platform_admin=False)
    with pytest.raises(HTTPException) as exc:
        require_platform_admin(auth)
    assert exc.value.status_code == 403


def test_require_platform_admin_with_passes():
    auth = _auth_context(is_platform_admin=True)
    assert require_platform_admin(auth) == auth
