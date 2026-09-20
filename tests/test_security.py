from __future__ import annotations

"""Tests de seguridad: validación de PDF (magic bytes) y handler global de 500."""

import pytest
from fastapi.testclient import TestClient

from app.services.documents_service import _validate_pdf
from app.main import create_app
from app.core.security import get_auth_context
from types import SimpleNamespace
from fastapi import HTTPException


def test_validate_pdf_rejects_wrong_content_type():
    with pytest.raises(Exception) as exc:
        _validate_pdf(b"%PDF-1.7 ...", "text/html")
    assert exc.value.status_code == 400


def test_validate_pdf_rejects_bad_magic_bytes():
    with pytest.raises(Exception) as exc:
        _validate_pdf(b"NOTAPDF......", "application/pdf")
    assert exc.value.status_code == 400


def test_validate_pdf_accepts_valid():
    _validate_pdf(b"%PDF-1.7\n...", "application/pdf")


def test_inactive_user_rejected(monkeypatch):

    class FakeAuth:
        def get_user(self, token):
            return SimpleNamespace(user=SimpleNamespace(id="u1", email="a@t", user_metadata={}))

    class FakeSupabase:
        auth = FakeAuth()

    class FakeUsersRepo:
        def get_user_by_external_auth_id(self, eid):
            return {"is_active": False}

    monkeypatch.setattr("app.core.supabase.get_supabase_client", lambda: FakeSupabase())
    monkeypatch.setattr("app.core.security.UsersRepository", lambda: FakeUsersRepo())
    try:
        get_auth_context(authorization="Bearer some.jwt.token")
        raise AssertionError("debería haber lanzado 401")
    except HTTPException as exc:
        assert exc.status_code == 401
        assert "Inactive" in exc.detail


def test_global_500_handler_returns_clean_json():
    app = create_app()

    @app.get("/_boom")
    def boom():
        raise RuntimeError("secret detail")

    resp = TestClient(app, raise_server_exceptions=False).get("/_boom")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert "secret" not in resp.text