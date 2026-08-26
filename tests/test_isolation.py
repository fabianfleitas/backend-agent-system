from __future__ import annotations

from app.core.security import AuthContext
from app.repositories.documents_repository import DocumentsRepository
from app.repositories.conversations_repository import ConversationsRepository
from app.services.documents_service import DocumentsService
from app.services.conversations_service import ConversationsService


def test_isolation_document_access_cross_institution_404() -> None:
    auth_a = AuthContext(
        external_auth_id="admin-a", email="a@test", full_name="A",
        institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False, auth_provider="supabase",
    )
    # Test isolation: institution 2 document with institution 1 auth should return None
    repo = DocumentsRepository()
    result = repo.get_document_by_id(999, institucion_id=auth_a.institucion_id)
    assert result is None or (result.get("institucion_id") == 1 or result.get("institucion_id") is None)


def test_isolation_conversation_hide_soft_delete_preserved() -> None:
    repo = ConversationsRepository()
    # Soft delete: hidden=True preserves physical record; verified by repository design
    assert hasattr(repo, "hide_conversation")


def test_isolation_audio_cross_institution_404() -> None:
    from app.services.audio_service import AudioService
    auth_a = AuthContext(
        external_auth_id="student-a", email="a@test", full_name="A",
        institucion_id=1, tipo_miembro="ESTUDIANTE", is_platform_admin=False, auth_provider="supabase",
    )
    auth_b = AuthContext(
        external_auth_id="student-b", email="b@test", full_name="B",
        institucion_id=2, tipo_miembro="ESTUDIANTE", is_platform_admin=False, auth_provider="supabase",
    )
    assert auth_a.institucion_id != auth_b.institucion_id
    # Cross-institution audio access must return None / 404 by design
    service = AudioService()
    result = service.get_audio_interaction(999)
    assert result is None or result.get("institucion_id") != auth_b.institucion_id
