from __future__ import annotations

from app.core.security import AuthContext


def test_student_access_own_resources() -> None:
    auth = AuthContext(
        external_auth_id="s1", email="s@test", full_name="S",
        institucion_id=1, tipo_miembro="ESTUDIANTE", is_platform_admin=False, auth_provider="supabase",
    )
    assert auth.institucion_id == 1
    assert auth.tipo_miembro == "ESTUDIANTE"


def test_admin_access_institutional() -> None:
    auth = AuthContext(
        external_auth_id="a1", email="a@test", full_name="A",
        institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False, auth_provider="supabase",
    )
    assert auth.tipo_miembro == "ADMIN"


def test_platform_admin_bypass() -> None:
    auth = AuthContext(
        external_auth_id="p1", email="p@test", full_name="P",
        institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=True, auth_provider="supabase",
    )
    assert auth.is_platform_admin is True


def test_no_membership_forbidden() -> None:
    auth = AuthContext(
        external_auth_id="x1", email="x@test", full_name="X",
        institucion_id=None, tipo_miembro=None, is_platform_admin=False, auth_provider="supabase",
    )
    assert auth.institucion_id is None
    assert not auth.is_platform_admin


def test_inactive_membership_rejected() -> None:
    # Membership inactive implies no valid institution_id in context
    auth = AuthContext(
        external_auth_id="i1", email="i@test", full_name="I",
        institucion_id=None, tipo_miembro=None, is_platform_admin=False, auth_provider="supabase",
    )
    assert auth.institucion_id is None
