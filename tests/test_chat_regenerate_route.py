from __future__ import annotations

"""Ruta POST /api/chat/regenerate (S11): regenera la última respuesta in-place."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat.routes import router as chat_router, _get_chat_service
from app.core.security import AuthContext, get_auth_context


class _FakeChatService:
    def __init__(self, result=None, none=False) -> None:
        self.result = result
        self.none = none
        self.calls = []

    def regenerate(self, auth, conversation_id):
        self.calls.append((auth, conversation_id))
        if self.none:
            return None
        return self.result


def _auth() -> AuthContext:
    return AuthContext(external_auth_id="student-1", institucion_id=1, tipo_miembro="ESTUDIANTE", is_platform_admin=False)


def _app(fake: _FakeChatService):
    app = FastAPI()
    app.include_router(chat_router, prefix="/api/chat")
    app.dependency_overrides[get_auth_context] = lambda: _auth()
    app.dependency_overrides[_get_chat_service] = lambda: fake
    return app


def test_regenerate_route_ok() -> None:
    assistant = {
        "id": 9,
        "conversacion_id": 1,
        "rol_mensaje": "ASSISTANT",
        "contenido_texto": "Respuesta regenerada.",
        "proveedor_ia": "OpenRouter",
        "modelo_ia": "fake-llm",
        "tokens_input": 5,
        "tokens_output": 3,
        "tiempo_respuesta_ms": 120,
        "fecha_envio": "2026-09-22T00:00:00Z",
        "audit_id": None,
    }
    fake = _FakeChatService(
        {
            "conversation_id": 1,
            "response": "Respuesta regenerada.",
            "sources": [],
            "audit_id": "00000000-0000-0000-0000-000000000001",
            "assistant_message": assistant,
        }
    )
    app = _app(fake)
    resp = TestClient(app).post("/api/chat/regenerate", json={"conversation_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "Respuesta regenerada."
    assert body["assistant_message"]["contenido_texto"] == "Respuesta regenerada."
    assert len(fake.calls) == 1


def test_regenerate_route_404_sin_turno() -> None:
    app = _app(_FakeChatService(none=True))
    resp = TestClient(app).post("/api/chat/regenerate", json={"conversation_id": 99})
    assert resp.status_code == 404