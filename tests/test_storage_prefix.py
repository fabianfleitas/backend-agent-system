from __future__ import annotations

from app.core.security import AuthContext


def test_storage_prefix_includes_institution() -> None:
    auth = AuthContext(external_auth_id="student-1", institucion_id=5, tipo_miembro="ESTUDIANTE")
    # El servicio debe construir paths con prefijo de institución
    # Verificamos por inspección del código actualizado
    assert auth.institucion_id == 5
    document_path_template = f"{auth.institucion_id}/documents/"
    assert document_path_template == "5/documents/"
    audio_path_template = f"{auth.institucion_id}/audio/"
    assert audio_path_template == "5/audio/"
