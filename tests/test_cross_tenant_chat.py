from __future__ import annotations

from app.core.security import AuthContext
from app.services.chat_service import ChatService


def test_chat_cross_tenant_conversation_ownership():
    auth_a = AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ESTUDIANTE")
    auth_b = AuthContext(external_auth_id="b", institucion_id=2, tipo_miembro="ESTUDIANTE")
    srv = ChatService()
    # Intentar acceder a conversación de A con auth B debe devolver None por ownership/inst
    result = srv.get_owned_conversation(999, auth_b.external_auth_id, auth_b.institucion_id)
    assert result is None
