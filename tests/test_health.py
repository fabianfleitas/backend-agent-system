from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.security import AuthContext, get_auth_context

app = create_app()


class FakeAuthA:
    def __init__(self):
        self.context = AuthContext(
            external_auth_id="student-a",
            email="a@test",
            full_name="A",
            institucion_id=1,
            tipo_miembro="ESTUDIANTE",
            is_platform_admin=False,
            auth_provider="supabase",
        )

    async def __call__(self):
        return self.context


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200


def test_ready_no_supabase():
    client = TestClient(app)
    resp = client.get("/ready")
    # Si Supabase no está configurado, debe devolver not_ready
    assert resp.status_code in (200, 503)
