from __future__ import annotations
from fastapi.testclient import TestClient
from app.main import create_app

def test_feedback_requires_auth() -> None:
    client = TestClient(create_app())
    resp = client.post("/api/chat/feedback")
    assert resp.status_code in (401, 403)
