from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import settings
from app.integrations.embeddings_client import (
    EmbeddingsClient,
    OpenAIEmbeddingsClient,
)
from app.services.chunking_service import Chunk

logger = logging.getLogger(__name__)


@dataclass
class EmbeddedChunk:
    chunk_index: int
    page_number: int
    text: str
    char_count: int
    token_count: int
    embedding: List[float]
    embedding_model: str


@dataclass
class QueryEmbeddingResult:
    embedding: Optional[List[float]] = None
    dimensions: int = 0
    model: str = ""
    ok: bool = True
    error: Optional[str] = None


@dataclass
class EmbeddingResult:
    embedded_chunks: List[EmbeddedChunk] = field(default_factory=list)
    total: int = 0
    total_tokens: int = 0
    dimensions: int = 0
    model: str = ""
    elapsed_ms: float = 0.0
    ok: bool = True
    error: Optional[str] = None


class EmbeddingService:
    def __init__(
        self,
        client: Optional[EmbeddingsClient] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_tokens_per_chunk: Optional[int] = None,
    ) -> None:
        self.client = client or OpenAIEmbeddingsClient(
            api_key=settings.openai_api_key or "",
            dimensions=settings.embedding_dimensions,
            timeout=settings.embedding_request_timeout,
            max_retries=settings.embedding_max_retries,
        )
        self.model = model or settings.embedding_model
        self.batch_size = batch_size or settings.embedding_batch_size
        self.max_tokens_per_chunk = max_tokens_per_chunk or settings.embedding_max_tokens_per_chunk
        self.dimensions = settings.embedding_dimensions

    def embed_chunks(self, chunks: List[Chunk]) -> EmbeddingResult:
        result = EmbeddingResult(model=self.model)
        eligible = [
            c
            for c in chunks
            if c.text.strip() and c.token_count <= self.max_tokens_per_chunk
        ]
        skipped = [
            c
            for c in chunks
            if c.text.strip() and c.token_count > self.max_tokens_per_chunk
        ]
        for chunk in skipped:
            logger.warning(
                "Skipping chunk over token limit chunk_index=%s token_count=%s max_tokens=%s",
                chunk.chunk_index,
                chunk.token_count,
                self.max_tokens_per_chunk,
            )
        if not eligible:
            logger.info("Embedding skipped: no eligible chunks model=%s", self.model)
            return result

        start = time.perf_counter()
        try:
            embedded: List[EmbeddedChunk] = []
            total_tokens = 0
            for offset in range(0, len(eligible), self.batch_size):
                batch = eligible[offset : offset + self.batch_size]
                vectors = self.client.embed([c.text for c in batch], self.model)
                for chunk, vector in zip(batch, vectors):
                    embedded.append(
                        EmbeddedChunk(
                            chunk_index=chunk.chunk_index,
                            page_number=chunk.page_number,
                            text=chunk.text,
                            char_count=chunk.char_count,
                            token_count=chunk.token_count,
                            embedding=vector,
                            embedding_model=self.model,
                        )
                    )
                    total_tokens += chunk.token_count
            result.embedded_chunks = embedded
            result.total = len(embedded)
            result.total_tokens = total_tokens
            result.dimensions = self.dimensions
        except Exception as exc:
            result.ok = False
            result.error = str(exc)
            result.embedded_chunks = []
            result.total = 0
            result.total_tokens = 0
            logger.error(
                "Embedding failed model=%s error=%s",
                self.model,
                exc,
            )
            return result

        result.elapsed_ms = (time.perf_counter() - start) * 1000.0
        batches = (len(eligible) + self.batch_size - 1) // self.batch_size
        logger.info(
            "Embedding ok model=%s total=%s total_tokens=%s dimensions=%s batches=%s elapsed_ms=%.1f",
            self.model,
            result.total,
            result.total_tokens,
            result.dimensions,
            batches,
            result.elapsed_ms,
        )
        return result

    def embed_query(self, text: str) -> QueryEmbeddingResult:
        result = QueryEmbeddingResult(model=self.model)
        if not text.strip():
            result.ok = False
            result.error = "empty query"
            return result
        try:
            vectors = self.client.embed([text], self.model)
            result.embedding = list(vectors[0])
            result.dimensions = self.dimensions
        except Exception as exc:
            result.ok = False
            result.error = str(exc)
            logger.error(
                "Query embedding failed model=%s text_len=%s error=%s",
                self.model,
                len(text),
                exc,
            )
        return result