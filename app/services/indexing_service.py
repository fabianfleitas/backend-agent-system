from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from app.core.config import settings
from app.integrations.pdf_extractor import extract_text_from_pdf
from app.repositories.chunks_repository import ChunksRepository
from app.repositories.documents_repository import DocumentsRepository
from app.repositories.embeddings_repository import EmbeddingsRepository, vector_to_pgstring
from app.repositories.storage_repository import StorageRepository
from app.services.chunking_service import PageText, chunk_pages
from app.services.embedding_service import EmbeddingResult, EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class IndexingResult:
    version_id: int
    status: str
    total_chunks: int = 0
    total_tokens: int = 0
    embedding_model: str = ""
    elapsed_ms: float = 0.0
    ok: bool = False
    error: Optional[str] = None


class IndexingService:
    def __init__(
        self,
        chunks_repository: Optional[ChunksRepository] = None,
        embeddings_repository: Optional[EmbeddingsRepository] = None,
        documents_repository: Optional[DocumentsRepository] = None,
        storage_repository: Optional[StorageRepository] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self.chunks_repository = chunks_repository or ChunksRepository()
        self.embeddings_repository = embeddings_repository or EmbeddingsRepository()
        self.documents_repository = documents_repository or DocumentsRepository()
        self.storage_repository = storage_repository or StorageRepository()
        self.embedding_service = embedding_service or EmbeddingService()

    def index_version(self, version_id: int, file_bytes: Optional[bytes] = None) -> IndexingResult:
        start = time.perf_counter()
        version = self.documents_repository.get_version_by_id(version_id)
        if not version:
            return IndexingResult(
                version_id=version_id,
                status="FAILED",
                ok=False,
                error="version not found",
            )
        self.documents_repository.update_version(version_id, status="PROCESSING", error_message=None)

        try:
            pages, texto_extraido = self._resolve_text(version, file_bytes)
            if not pages:
                return self._finish_failed(
                    version_id, "extraction produced no pages", start
                )
            chunk_result = chunk_pages(pages)
            if not chunk_result.ok or chunk_result.total_chunks == 0:
                return self._finish_failed(
                    version_id, chunk_result.error or "chunking produced no chunks", start
                )
            logger.info(
                "Indexing chunked version_id=%s total_chunks=%s total_tokens=%s",
                version_id,
                chunk_result.total_chunks,
                chunk_result.total_tokens,
            )

            embedding_result = self.embedding_service.embed_chunks(chunk_result.chunks)
            if not embedding_result.ok or embedding_result.total == 0:
                return self._finish_failed(
                    version_id, embedding_result.error or "embedding produced no vectors", start
                )

            self._persist(version_id, embedding_result)
        except Exception as exc:
            logger.error("Indexing persist failed version_id=%s error=%s", version_id, exc)
            return self._finish_failed(version_id, str(exc), start)

        update_fields: dict = {
            "status": "READY",
            "total_chunks": embedding_result.total,
            "embedding_model": embedding_result.model,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        if texto_extraido is not None:
            update_fields["texto_extraido"] = texto_extraido
        self.documents_repository.update_version(version_id, **update_fields)
        elapsed = (time.perf_counter() - start) * 1000.0
        logger.info(
            "Indexing done version_id=%s status=READY total_chunks=%s total_tokens=%s model=%s elapsed_ms=%.1f",
            version_id,
            embedding_result.total,
            embedding_result.total_tokens,
            embedding_result.model,
            elapsed,
        )
        return IndexingResult(
            version_id=version_id,
            status="READY",
            total_chunks=embedding_result.total,
            total_tokens=embedding_result.total_tokens,
            embedding_model=embedding_result.model,
            elapsed_ms=elapsed,
            ok=True,
        )

    def _resolve_text(
        self, version: dict, file_bytes: Optional[bytes]
    ) -> tuple[list[PageText], Optional[str]]:
        if file_bytes is not None:
            extraction = extract_text_from_pdf(file_bytes)
            if not extraction.ok:
                raise RuntimeError(extraction.error or "pdf extraction failed")
            pages = [
                PageText(page.page_number, page.text) for page in extraction.pages
            ]
            texto_extraido = "\n\n".join(page.text for page in extraction.pages)
            return pages, texto_extraido

        existing_text = version.get("texto_extraido")
        if existing_text:
            return [PageText(0, existing_text)], None

        if version.get("ruta_archivo"):
            file_bytes = self.storage_repository.download_document(version["ruta_archivo"])
            extraction = extract_text_from_pdf(file_bytes)
            if not extraction.ok:
                raise RuntimeError(extraction.error or "pdf extraction failed")
            pages = [
                PageText(page.page_number, page.text) for page in extraction.pages
            ]
            texto_extraido = "\n\n".join(page.text for page in extraction.pages)
            return pages, texto_extraido

        raise RuntimeError("no file and no extracted text available for version")

    def _persist(self, version_id: int, embedding_result: EmbeddingResult) -> None:
        self.chunks_repository.delete_by_version(version_id)
        chunk_rows = [
            {
                "documento_version_id": version_id,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "chunk_text": chunk.text,
                "token_count": chunk.token_count,
            }
            for chunk in embedding_result.embedded_chunks
        ]
        inserted_chunks = self.chunks_repository.insert_chunks(version_id, chunk_rows)
        id_by_index: dict[int, int] = {}
        for row in inserted_chunks:
            id_by_index[int(row["chunk_index"])] = int(row["id"])
        embedding_rows = [
            {
                "chunk_id": id_by_index[chunk.chunk_index],
                "embedding": vector_to_pgstring(chunk.embedding),
                "embedding_model": chunk.embedding_model,
            }
            for chunk in embedding_result.embedded_chunks
        ]
        self.embeddings_repository.insert_embeddings(embedding_rows)

    def _finish_failed(self, version_id: int, error: str, start: float) -> IndexingResult:
        self.documents_repository.update_version(version_id, status="FAILED", error_message=error)
        elapsed = (time.perf_counter() - start) * 1000.0
        logger.warning(
            "Indexing failed version_id=%s error=%s elapsed_ms=%.1f",
            version_id,
            error,
            elapsed,
        )
        return IndexingResult(
            version_id=version_id,
            status="FAILED",
            elapsed_ms=elapsed,
            ok=False,
            error=error,
        )