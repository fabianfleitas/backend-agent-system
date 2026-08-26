from __future__ import annotations

import pytest

from app.services.retrieval_service import RetrievalService, RetrievalResult
from app.repositories.retrieval_repository import RetrievalRepository
from app.services.config_service import ConfigService


class FakeRetrievalRepo:
    def __init__(self, chunks_by_inst: dict) -> None:
        self.chunks_by_inst = chunks_by_inst

    def match_chunks(self, query_embedding, match_count, similarity_threshold, institucion_id):
        return self.chunks_by_inst.get(institucion_id, [])


class FakeEmbeddingService:
    def __init__(self, embedding) -> None:
        self.embedding = embedding

    def embed_query(self, query):
        return type("R", (), {"ok": True, "embedding": self.embedding, "model": "fake", "error": None})()


def test_retrieval_isolation_filters_by_institution():
    chunk_1 = {"chunk_id": 1, "document_id": 7, "document_version_id": 6, "document_title": "Reglamento.pdf", "page_number": 3, "chunk_text": "texto", "similarity": 0.85}
    chunk_2 = {"chunk_id": 2, "document_id": 99, "document_version_id": 10, "document_title": "Otro.pdf", "page_number": 1, "chunk_text": "texto2", "similarity": 0.72}
    repo = FakeRetrievalRepo({1: [chunk_1], 2: [chunk_2]})
    # Fake ConfigService para evitar conexión real a Supabase
    fake_config = ConfigService()
    fake_config.repo = None
    fake_config._cache = {}
    service = RetrievalService(retrieval_repository=repo, embedding_service=FakeEmbeddingService([0.1]*1536), config_service=fake_config)
    result = service.retrieve("consulta", institucion_id=1)
    assert result.ok
    assert len(result.chunks) == 1
    assert result.chunks[0].chunk_id == 1


def test_retrieval_isolation_without_institution_id_errors():
    repo = FakeRetrievalRepo({})
    service = RetrievalService(retrieval_repository=repo, embedding_service=FakeEmbeddingService([0.1]*1536))
    result = service.retrieve("consulta")
    assert not result.ok
    assert "institution_id required" in result.error
