from __future__ import annotations

from typing import List, Optional

from app.repositories.retrieval_repository import RetrievalRepository
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import RetrievalService

DIMENSIONS = 1536


class FakeEmbeddingsClient:
    def __init__(self, dimensions: int = DIMENSIONS, fail_with: Optional[Exception] = None) -> None:
        self.dimensions = dimensions
        self.fail_with = fail_with
        self.calls: List[str] = []

    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        self.calls.extend(texts)
        if self.fail_with is not None:
            raise self.fail_with
        return [[float(len(text))] * self.dimensions for text in texts]


class FakeRetrievalRepository:
    def __init__(self, rows: Optional[List[dict]] = None, fail_with: Optional[Exception] = None) -> None:
        self.rows = rows or []
        self.fail_with = fail_with
        self.calls: List[dict] = []

    def match_chunks(self, query_embedding: List[float], match_count: int, similarity_threshold: float, institucion_id: Optional[int] = None) -> List[dict]:
        self.calls.append(
            {
                "query_embedding": query_embedding,
                "match_count": match_count,
                "similarity_threshold": similarity_threshold,
                "institucion_id": institucion_id,
            }
        )
        if self.fail_with is not None:
            raise self.fail_with
        return list(self.rows)


def _row(chunk_id: int, similarity: float) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": 7,
        "document_version_id": 6,
        "document_title": "Reglamento Académico.pdf",
        "page_number": 3,
        "chunk_text": "ARTICULO 10.- La matrícula requiere documentacion vigente.",
        "similarity": similarity,
    }


def _make_service(rows: Optional[List[dict]] = None, fail_with: Optional[Exception] = None) -> tuple[RetrievalService, FakeRetrievalRepository, FakeEmbeddingsClient]:
    repo = FakeRetrievalRepository(rows, fail_with)
    client = FakeEmbeddingsClient()
    embedding_service = EmbeddingService(client=client, model="fake-model")
    service = RetrievalService(
        embedding_service=embedding_service,
        retrieval_repository=repo,
        match_count=5,
        similarity_threshold=0.30,
    )
    return service, repo, client


def test_retrieve_maps_rows() -> None:
    service, repo, _ = _make_service([_row(10, 0.85), _row(11, 0.72)])
    result = service.retrieve("requisitos de matrícula", institucion_id=1)
    assert result.ok
    assert result.error is None
    assert result.total == 2
    assert [c.chunk_id for c in result.chunks] == [10, 11]
    chunk = result.chunks[0]
    assert chunk.document_title == "Reglamento Académico.pdf"
    assert chunk.document_id == 7
    assert chunk.document_version_id == 6
    assert chunk.page_number == 3
    assert chunk.chunk_text.startswith("ARTICULO")
    assert chunk.similarity == 0.85
    assert result.elapsed_ms >= 0


def test_retrieve_sorts_by_similarity_desc() -> None:
    service, _, _ = _make_service([_row(1, 0.40), _row(2, 0.99), _row(3, 0.30)])
    result = service.retrieve("consulta", institucion_id=1)
    assert [c.chunk_id for c in result.chunks] == [2, 1, 3]


def test_client_filters_below_threshold() -> None:
    service, _, _ = _make_service([_row(1, 0.85), _row(2, 0.12)])
    result = service.retrieve("consulta", institucion_id=1)
    assert result.ok
    assert result.total == 1
    assert [c.chunk_id for c in result.chunks] == [1]


def test_threshold_config_passed_to_repo() -> None:
    service, repo, _ = _make_service([_row(1, 0.80)])
    service.retrieve("consulta", institucion_id=1)
    call = repo.calls[-1]
    assert call["match_count"] == 5
    assert call["similarity_threshold"] == 0.30
    assert call["institucion_id"] == 1
    assert len(call["query_embedding"]) == DIMENSIONS


def test_embedding_failure_returns_not_ok() -> None:
    repo = FakeRetrievalRepository(rows=[_row(1, 0.9)])
    embedding_service = EmbeddingService(client=FakeEmbeddingsClient(fail_with=RuntimeError("openai down")), model="fake-model")
    service = RetrievalService(
        embedding_service=embedding_service,
        retrieval_repository=repo,
        similarity_threshold=0.30,
    )
    result = service.retrieve("consulta", institucion_id=1)
    assert not result.ok
    assert result.error == "openai down"
    assert result.total == 0
    assert repo.calls == []


def test_rpc_failure_returns_not_ok() -> None:
    service, _, _ = _make_service(fail_with=RuntimeError("db unavailable"))
    result = service.retrieve("consulta", institucion_id=1)
    assert not result.ok
    assert result.error == "db unavailable"
    assert result.total == 0
    assert result.chunks == []


def test_empty_query_returns_not_ok() -> None:
    service, repo, _ = _make_service([_row(1, 0.9)])
    result = service.retrieve("   ", institucion_id=1)
    assert not result.ok
    assert result.error == "empty query"
    assert repo.calls == []


def test_no_rows_ok_without_error() -> None:
    service, _, _ = _make_service([])
    result = service.retrieve("consulta fuera de dominio", institucion_id=1)
    assert result.ok
    assert result.error is None
    assert result.total == 0
    assert result.chunks == []