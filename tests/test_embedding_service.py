from __future__ import annotations

from typing import List

from app.integrations.embeddings_client import EmbeddingsClient
from app.services.chunking_service import Chunk
from app.services.embedding_service import EmbeddingService

DIMENSIONS = 1536


class FakeEmbeddingsClient:
    def __init__(self, dimensions: int = DIMENSIONS, fail_with: Exception | None = None) -> None:
        self.dimensions = dimensions
        self.fail_with = fail_with
        self.calls: List[List[str]] = []

    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        self.calls.append(texts)
        if self.fail_with is not None:
            raise self.fail_with
        return [[float(len(text))] * self.dimensions for text in texts]


def _chunk(index: int, text: str, token_count: int | None = None) -> Chunk:
    return Chunk(
        chunk_index=index,
        page_number=1,
        text=text,
        char_count=len(text),
        token_count=token_count if token_count is not None else len(text) // 4,
    )


def test_embed_chunks_returns_embeddings() -> None:
    client = FakeEmbeddingsClient()
    service = EmbeddingService(client=client, model="fake-model")
    chunks = [_chunk(0, "reglamento academico"), _chunk(1, "matricula anual")]
    result = service.embed_chunks(chunks)
    assert result.ok
    assert result.total == 2
    assert result.model == "fake-model"
    assert result.dimensions == DIMENSIONS
    assert len(result.embedded_chunks) == 2
    for embedded in result.embedded_chunks:
        assert len(embedded.embedding) == DIMENSIONS
        assert embedded.embedding_model == "fake-model"


def test_chunk_index_and_metadata_preserved() -> None:
    client = FakeEmbeddingsClient()
    service = EmbeddingService(client=client, model="fake-model")
    chunks = [_chunk(5, "primero"), _chunk(8, "segundo")]
    result = service.embed_chunks(chunks)
    assert [e.chunk_index for e in result.embedded_chunks] == [5, 8]
    assert [e.text for e in result.embedded_chunks] == ["primero", "segundo"]


def test_empty_chunks() -> None:
    client = FakeEmbeddingsClient()
    service = EmbeddingService(client=client, model="fake-model")
    result = service.embed_chunks([])
    assert result.ok
    assert result.total == 0
    assert result.embedded_chunks == []
    assert client.calls == []


def test_blank_chunks_skipped() -> None:
    client = FakeEmbeddingsClient()
    service = EmbeddingService(client=client, model="fake-model")
    chunks = [_chunk(0, ""), _chunk(1, "   "), _chunk(2, "contenido valido")]
    result = service.embed_chunks(chunks)
    assert result.ok
    assert result.total == 1
    assert [e.chunk_index for e in result.embedded_chunks] == [2]


def test_oversized_chunk_skipped() -> None:
    client = FakeEmbeddingsClient()
    service = EmbeddingService(client=client, model="fake-model", max_tokens_per_chunk=100)
    chunks = [_chunk(0, "corto", token_count=50), _chunk(1, "largo", token_count=500)]
    result = service.embed_chunks(chunks)
    assert result.ok
    assert result.total == 1
    assert [e.chunk_index for e in result.embedded_chunks] == [0]


def test_client_error_sets_ok_false() -> None:
    client = FakeEmbeddingsClient(fail_with=RuntimeError("API down"))
    service = EmbeddingService(client=client, model="fake-model")
    chunks = [_chunk(0, "algo")]
    result = service.embed_chunks(chunks)
    assert not result.ok
    assert result.error == "API down"
    assert result.embedded_chunks == []
    assert result.total == 0


def test_batching_splits_calls() -> None:
    client = FakeEmbeddingsClient()
    service = EmbeddingService(client=client, model="fake-model", batch_size=64)
    chunks = [_chunk(i, f"texto de prueba {i} con contenido academico") for i in range(130)]
    result = service.embed_chunks(chunks)
    assert result.ok
    assert result.total == 130
    assert [len(call) for call in client.calls] == [64, 64, 2]


def test_elapsed_ms_recorded() -> None:
    client = FakeEmbeddingsClient()
    service = EmbeddingService(client=client, model="fake-model")
    chunks = [_chunk(0, "contenido")]
    result = service.embed_chunks(chunks)
    assert result.elapsed_ms >= 0


def test_total_tokens_summed() -> None:
    client = FakeEmbeddingsClient()
    service = EmbeddingService(client=client, model="fake-model")
    chunks = [_chunk(0, "uno", token_count=10), _chunk(1, "dos", token_count=20)]
    result = service.embed_chunks(chunks)
    assert result.total_tokens == 30


def test_embed_query_returns_vector() -> None:
    client = FakeEmbeddingsClient()
    service = EmbeddingService(client=client, model="fake-model")
    result = service.embed_query("¿cuál es el requisito de matrícula?")
    assert result.ok
    assert result.error is None
    assert result.embedding is not None
    assert len(result.embedding) == DIMENSIONS
    assert result.dimensions == DIMENSIONS
    assert result.model == "fake-model"
    assert client.calls == [["¿cuál es el requisito de matrícula?"]]


def test_embed_query_blank_text_fails() -> None:
    client = FakeEmbeddingsClient()
    service = EmbeddingService(client=client, model="fake-model")
    for blank in ("", "   "):
        result = service.embed_query(blank)
        assert not result.ok
        assert result.error == "empty query"
        assert result.embedding is None
    assert client.calls == []


def test_embed_query_client_error_sets_ok_false() -> None:
    client = FakeEmbeddingsClient(fail_with=RuntimeError("API down"))
    service = EmbeddingService(client=client, model="fake-model")
    result = service.embed_query("consulta institucional")
    assert not result.ok
    assert result.error == "API down"
    assert result.embedding is None