from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import settings
from app.repositories.retrieval_repository import RetrievalRepository
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_version_id: int
    document_title: str
    page_number: int
    chunk_text: str
    similarity: float


@dataclass
class RetrievalResult:
    chunks: List[RetrievedChunk] = field(default_factory=list)
    total: int = 0
    elapsed_ms: float = 0.0
    ok: bool = True
    error: Optional[str] = None


class RetrievalService:
    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        retrieval_repository: Optional[RetrievalRepository] = None,
        match_count: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.retrieval_repository = retrieval_repository or RetrievalRepository()
        self.match_count = match_count or settings.retrieval_match_count
        self.similarity_threshold = (
            similarity_threshold if similarity_threshold is not None else settings.retrieval_similarity_threshold
        )

    def retrieve(self, query: str) -> RetrievalResult:
        start = time.perf_counter()
        result = RetrievalResult()
        if not query.strip():
            result.ok = False
            result.error = "empty query"
            return result

        embedding = self.embedding_service.embed_query(query)
        if not embedding.ok or not embedding.embedding:
            result.ok = False
            result.error = embedding.error or "query embedding failed"
            logger.warning(
                "Retrieval skipped query_len=%s reason=%s",
                len(query),
                result.error,
            )
            return result

        try:
            rows = self.retrieval_repository.match_chunks(
                query_embedding=embedding.embedding,
                match_count=self.match_count,
                similarity_threshold=self.similarity_threshold,
            )
        except Exception as exc:
            result.ok = False
            result.error = str(exc)
            logger.error(
                "Retrieval RPC failed model=%s error=%s",
                embedding.model,
                exc,
            )
            return result

        chunks = [self._to_chunk(row) for row in rows]
        chunks = self._apply_client_filter(chunks)
        chunks.sort(key=lambda c: c.similarity, reverse=True)
        result.chunks = chunks
        result.total = len(chunks)
        result.elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "Retrieval done model=%s total=%s top_similarity=%s threshold=%.3f elapsed_ms=%.1f",
            embedding.model,
            result.total,
            f"{chunks[0].similarity:.4f}" if chunks else "n/a",
            self.similarity_threshold,
            result.elapsed_ms,
        )
        return result

    def _to_chunk(self, row: dict) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=int(row["chunk_id"]),
            document_id=int(row["document_id"]),
            document_version_id=int(row["document_version_id"]),
            document_title=row.get("document_title") or "",
            page_number=int(row["page_number"] or 0),
            chunk_text=row.get("chunk_text") or "",
            similarity=float(row.get("similarity") or 0.0),
        )

    def _apply_client_filter(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        return [c for c in chunks if c.similarity >= self.similarity_threshold]