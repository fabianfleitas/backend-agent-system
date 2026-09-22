from __future__ import annotations

from app.core.security import AuthContext
from app.services.documents_service import DocumentsService


class FakeDocRepo:
    def __init__(self, docs: dict) -> None:
        self.docs = docs  # {institucion_id: [documento]}

    def get_document_by_id(self, documento_id: int, institucion_id: int = None) -> dict | None:
        for d in self.docs.get(institucion_id, []):
            if d["id"] == documento_id:
                return d
        return None


class FakeStorageRepo:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def download_document(self, path: str) -> bytes:
        self.calls.append(path)
        if path == "no-existe":
            raise FileNotFoundError(path)
        return b"%PDF-content-fake"


def make_auth(institucion_id=1, tipo_miembro="ADMIN", is_platform_admin=False) -> AuthContext:
    return AuthContext(
        external_auth_id=f"admin-{institucion_id}",
        institucion_id=institucion_id,
        tipo_miembro=tipo_miembro,
        is_platform_admin=is_platform_admin,
    )


def _doc(id: int, institucion_id: int, versiones=None) -> dict:
    return {
        "id": id,
        "institucion_id": institucion_id,
        "titulo": f"Doc {id}",
        "activo": True,
        "documento_versiones": versiones or [
            {
                "id": 10,
                "numero_version": 1,
                "ruta_archivo": f"{institucion_id}/documents/abc.pdf",
                "es_version_activa": True,
                "original_filename": f"doc-{id}.pdf",
                "mime_type": "application/pdf",
            }
        ],
    }


def test_download_original_returns_content_filename_and_mime() -> None:
    repo = FakeDocRepo({1: [_doc(7, 1)]})
    storage = FakeStorageRepo()
    svc = DocumentsService(documents_repository=repo, storage_repository=storage)
    result = svc.download_original(7, make_auth(institucion_id=1))
    assert result is not None
    content, filename, mime_type, path = result
    assert content == b"%PDF-content-fake"
    assert filename == "doc-7.pdf"
    assert mime_type == "application/pdf"
    assert path.endswith("documents/abc.pdf")
    assert storage.calls == [f"1/documents/abc.pdf"]


def test_download_original_other_institution_none() -> None:
    repo = FakeDocRepo({2: [_doc(7, 2)]})
    storage = FakeStorageRepo()
    svc = DocumentsService(documents_repository=repo, storage_repository=storage)
    assert svc.download_original(7, make_auth(institucion_id=1)) is None
    assert storage.calls == []


def test_download_original_no_active_version_none() -> None:
    repo = FakeDocRepo({1: [{"id": 7, "institucion_id": 1, "titulo": "D", "activo": True, "documento_versiones": []}]})
    storage = FakeStorageRepo()
    svc = DocumentsService(documents_repository=repo, storage_repository=storage)
    assert svc.download_original(7, make_auth(institucion_id=1)) is None


def test_download_original_storage_error_none() -> None:
    versiones = [{
        "id": 10,
        "numero_version": 1,
        "ruta_archivo": "no-existe",
        "es_version_activa": True,
        "original_filename": "doc-7.pdf",
        "mime_type": "application/pdf",
    }]
    repo = FakeDocRepo({1: [{"id": 7, "institucion_id": 1, "titulo": "D", "activo": True, "documento_versiones": versiones}]})
    storage = FakeStorageRepo()
    svc = DocumentsService(documents_repository=repo, storage_repository=storage)
    assert svc.download_original(7, make_auth(institucion_id=1)) is None