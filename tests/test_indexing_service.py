from __future__ import annotations

from typing import Any, Dict, List, Optional

import fitz

from app.services.embedding_service import EmbeddingService
from app.services.indexing_service import IndexingService

DIMENSIONS = 1536


class FakeEmbeddingsClient:
    def __init__(self, dimensions: int = DIMENSIONS, fail_with: Optional[Exception] = None) -> None:
        self.dimensions = dimensions
        self.fail_with = fail_with
        self.calls: List[List[str]] = []

    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        self.calls.append(texts)
        if self.fail_with is not None:
            raise self.fail_with
        return [[float(len(text))] * self.dimensions for text in texts]


class FakeChunksRepository:
    def __init__(self) -> None:
        self.rows: List[dict] = []
        self.next_id = 1
        self.delete_calls = 0
        self.insert_calls = 0

    def insert_chunks(self, version_id: int, rows: List[dict]) -> List[dict]:
        self.insert_calls += 1
        inserted = []
        for row in rows:
            record = dict(row)
            record["id"] = self.next_id
            self.next_id += 1
            inserted.append(record)
        self.rows.extend(inserted)
        return inserted

    def delete_by_version(self, version_id: int) -> int:
        self.delete_calls += 1
        count = len([r for r in self.rows if r["documento_version_id"] == version_id])
        self.rows = [r for r in self.rows if r["documento_version_id"] != version_id]
        return count

    def list_by_version(self, version_id: int) -> List[dict]:
        return [r for r in self.rows if r["documento_version_id"] == version_id]


class FakeEmbeddingsRepository:
    def __init__(self) -> None:
        self.rows: List[dict] = []
        self.insert_calls = 0
        self.fail_with: Optional[Exception] = None

    def insert_embeddings(self, rows: List[dict]) -> List[dict]:
        self.insert_calls += 1
        if self.fail_with is not None:
            raise self.fail_with
        self.rows.extend(rows)
        return rows


class FakeDocumentsRepository:
    def __init__(self, version: Optional[dict] = None) -> None:
        self.version = version
        self.updates: List[Dict[str, Any]] = []
        self.calls: List[str] = []

    def get_version_by_id(self, version_id: int) -> Optional[dict]:
        self.calls.append("get_version_by_id")
        return self.version

    def update_version(self, version_id: int, **fields: Any) -> Optional[dict]:
        self.updates.append(fields)
        if self.version is not None:
            self.version = {**self.version, **fields}
        return self.version


class FakeStorageRepository:
    def __init__(self, content: Optional[bytes] = None) -> None:
        self.content = content
        self.download_calls = 0

    def download_document(self, path: str) -> bytes:
        self.download_calls += 1
        if self.content is None:
            raise RuntimeError("no file in storage")
        return self.content


def _make_pdf(texts: List[str]) -> bytes:
    doc = fitz.open()
    for text in texts:
        doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _make_service(
    version: Optional[dict] = None,
    storage_content: Optional[bytes] = None,
    embeddings_client: Optional[FakeEmbeddingsClient] = None,
    embeddings_repo: Optional[FakeEmbeddingsRepository] = None,
) -> tuple[IndexingService, FakeDocumentsRepository, FakeChunksRepository, FakeEmbeddingsRepository]:
    docs = FakeDocumentsRepository(version)
    chunks = FakeChunksRepository()
    embeddings = embeddings_repo or FakeEmbeddingsRepository()
    storage = FakeStorageRepository(storage_content)
    embedding_service = EmbeddingService(
        client=embeddings_client or FakeEmbeddingsClient(),
        model="fake-model",
    )
    service = IndexingService(
        chunks_repository=chunks,
        embeddings_repository=embeddings,
        documents_repository=docs,
        storage_repository=storage,
        embedding_service=embedding_service,
    )
    return service, docs, chunks, embeddings


def test_happy_path_upload_indexes_and_marks_ready() -> None:
    version = {"id": 1, "texto_extraido": None, "ruta_archivo": "documents/x.pdf", "status": "PENDING"}
    pdf = _make_pdf(
        [
            "ARTICULO 1.- El presente reglamento regula la matricula de todos los estudiantes.",
            "ARTICULO 2.- La matricula se realiza en linea cada semestre y requiere documentacion vigente.",
        ]
    )
    service, docs, chunks, _ = _make_service(version, storage_content=pdf)
    result = service.index_version(1, file_bytes=pdf)
    assert result.ok
    assert result.status == "READY"
    assert result.total_chunks >= 1
    assert result.total_tokens > 0
    assert result.embedding_model == "fake-model"
    assert docs.updates[0]["status"] == "PROCESSING"
    assert chunks.insert_calls == 1
    assert len(chunks.rows) == result.total_chunks
    final = docs.updates[-1]
    assert final["status"] == "READY"
    assert final["total_chunks"] == result.total_chunks
    assert final["embedding_model"] == "fake-model"
    assert final["indexed_at"] is not None
    assert final["texto_extraido"]


def test_embeddings_inserted_with_pgvector_string() -> None:
    version = {"id": 1, "texto_extraido": "ARTICULO 1.- Texto de prueba para indexar contenido academico."}
    service, _, _, embeddings = _make_service(version)
    result = service.index_version(1)
    assert result.ok
    assert embeddings.insert_calls == 1
    for row in embeddings.rows:
        assert row["embedding"].startswith("[")
        assert row["embedding"].endswith("]")
        assert row["embedding_model"] == "fake-model"
    assert len(embeddings.rows) == result.total_chunks


def test_embedding_failure_marks_failed_no_persist() -> None:
    version = {"id": 1, "texto_extraido": "ARTICULO 1.- Reglamento academico institucional vigente."}
    failing = FakeEmbeddingsClient(fail_with=RuntimeError("openai down"))
    service, docs, chunks, embeddings = _make_service(version, embeddings_client=failing)
    result = service.index_version(1)
    assert not result.ok
    assert result.status == "FAILED"
    assert result.error == "openai down"
    assert chunks.insert_calls == 0
    assert embeddings.insert_calls == 0
    assert docs.updates[-1]["status"] == "FAILED"
    assert docs.updates[-1]["error_message"] == "openai down"


def test_persist_failure_marks_failed() -> None:
    version = {"id": 1, "texto_extraido": "ARTICULO 1.- Contenido academico para indexacion."}
    emb_repo = FakeEmbeddingsRepository()
    emb_repo.fail_with = RuntimeError("db unavailable")
    service, docs, _, _ = _make_service(version, embeddings_repo=emb_repo)
    result = service.index_version(1)
    assert not result.ok
    assert result.status == "FAILED"
    assert docs.updates[-1]["status"] == "FAILED"


def test_version_not_found() -> None:
    service, _, _, _ = _make_service(version=None)
    result = service.index_version(999)
    assert not result.ok
    assert result.error == "version not found"
    assert result.status == "FAILED"


def test_reindex_uses_texto_extraido_without_download() -> None:
    version = {
        "id": 1,
        "texto_extraido": "ARTICULO 5.- La asistencia a clases es obligatoria y se evalua.",
        "ruta_archivo": "documents/x.pdf",
        "status": "PENDING",
    }
    service, docs, chunks, _ = _make_service(version, storage_content=_make_pdf(["ignored"]))
    result = service.index_version(1)
    assert result.ok
    assert result.status == "READY"
    assert all(chunk["page_number"] == 0 for chunk in chunks.rows)
    assert docs.updates[-1].get("texto_extraido") in (None, None) or "texto_extraido" not in docs.updates[-1]
    final = docs.updates[-1]
    assert final.get("texto_extraido") is None


def test_reindex_without_texto_downloads_and_extracts() -> None:
    version = {"id": 2, "texto_extraido": None, "ruta_archivo": "documents/y.pdf", "status": "FAILED"}
    long_text = (
        "ARTICULO 1.- El presente reglamento academico regula la matricula, la asistencia y la "
        "evaluacion continua de todos los estudiantes del sistema institucional. " * 3
    )
    long_text2 = (
        "ARTICULO 2.- Las normas de evaluacion continua consideran trabajos practicos, examenes "
        "parciales y un examen final obligatorio ante la secretaria academica. " * 3
    )
    pdf = _make_pdf([long_text, long_text2])
    service, docs, chunks, _ = _make_service(version, storage_content=pdf)
    storage = service.storage_repository
    assert storage.download_calls == 0
    result = service.index_version(2)
    assert result.ok
    assert storage.download_calls == 1
    assert any(chunk["page_number"] == 2 for chunk in chunks.rows)
    final = docs.updates[-1]
    assert final["status"] == "READY"
    assert final["texto_extraido"]


def test_idempotent_reindex_deletes_before_insert() -> None:
    version = {"id": 1, "texto_extraido": "ARTICULO 1.- Reglamento academico institucional para todos."}
    service, docs, chunks, _ = _make_service(version)
    first = service.index_version(1)
    second = service.index_version(1)
    assert first.ok and second.ok
    assert chunks.delete_calls == 2
    assert chunks.insert_calls == 2
    assert len(chunks.rows) == second.total_chunks