from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.services.text_cleaner import clean_page_text, normalize_for_dedup
from app.utils.tokens import count_tokens as _count_tokens

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
MIN_CHUNK_CHARS = 100
_PAGE_SEPARATOR = "\n\n"
_SEPARATORS = ["\n\n", "\n", ". ", ", ", " ", ""]
_STRUCTURAL_PATTERN = re.compile(r"(?im)^\s*(?:art[ií]culo|t[ií]tulo|cap[ií]tulo|secci[oó]n)\s+\S+")


@dataclass
class PageText:
    page_number: int
    text: str


@dataclass
class Chunk:
    chunk_index: int
    page_number: int
    text: str
    char_count: int
    token_count: int


@dataclass
class ChunkingResult:
    chunks: List[Chunk] = field(default_factory=list)
    total_chunks: int = 0
    total_tokens: int = 0
    total_chars: int = 0
    dropped_duplicate_pages: int = 0
    ok: bool = True
    error: Optional[str] = None


def chunk_pages(pages: List[PageText]) -> ChunkingResult:
    result = ChunkingResult()
    try:
        cleaned = [PageText(page.page_number, clean_page_text(page.text)) for page in pages]
        deduped, dropped = _deduplicate_pages(cleaned)
        result.dropped_duplicate_pages = dropped

        full_text, page_offsets = _join_pages(deduped)
        if not full_text.strip():
            return result

        segments = _structural_split(full_text)
        pieces: List[Tuple[str, int]] = []
        for text, start_offset in segments:
            pieces.extend(_recursive_split(text, start_offset, CHUNK_SIZE, CHUNK_OVERLAP))
        pieces = _merge_small_chunks(pieces)

        chunks: List[Chunk] = []
        for index, (text, start_offset) in enumerate(pieces):
            text = text.strip()
            if not text:
                continue
            chunks.append(
                Chunk(
                    chunk_index=index,
                    page_number=_page_for_offset(page_offsets, start_offset),
                    text=text,
                    char_count=len(text),
                    token_count=_count_tokens(text),
                )
            )

        result.chunks = chunks
        result.total_chunks = len(chunks)
        result.total_tokens = sum(chunk.token_count for chunk in chunks)
        result.total_chars = sum(chunk.char_count for chunk in chunks)
    except Exception as exc:
        result.ok = False
        result.error = str(exc)
        result.chunks = []
        result.total_chunks = 0
        result.total_tokens = 0
        result.total_chars = 0
        logger.error("Chunking failed: %s", exc)
    else:
        logger.info(
            "Chunking ok total_chunks=%s total_tokens=%s total_chars=%s dropped_duplicate_pages=%s",
            result.total_chunks,
            result.total_tokens,
            result.total_chars,
            result.dropped_duplicate_pages,
        )
    return result


def _deduplicate_pages(pages: List[PageText]) -> Tuple[List[PageText], int]:
    result: List[PageText] = []
    previous: Optional[str] = None
    dropped = 0
    for page in pages:
        normalized = normalize_for_dedup(page.text)
        if normalized and normalized == previous:
            dropped += 1
            logger.debug("Dropping duplicate page number=%s", page.page_number)
            continue
        previous = normalized
        result.append(page)
    return result, dropped


def _join_pages(pages: List[PageText]) -> Tuple[str, List[Tuple[int, int]]]:
    parts: List[str] = []
    offsets: List[Tuple[int, int]] = []
    cursor = 0
    for page in pages:
        offsets.append((cursor, page.page_number))
        parts.append(page.text)
        cursor += len(page.text) + len(_PAGE_SEPARATOR)
    return _PAGE_SEPARATOR.join(parts), offsets


def _structural_split(text: str) -> List[Tuple[str, int]]:
    matches = list(_STRUCTURAL_PATTERN.finditer(text))
    if not matches:
        return [_strip_leading(text, 0)]
    segments: List[Tuple[str, int]] = []
    start = 0
    for match in matches:
        if match.start() > start:
            segments.append(_strip_leading(text[start : match.start()], start))
        start = match.start()
    segments.append(_strip_leading(text[start:], start))
    return segments


def _strip_leading(text: str, start: int) -> Tuple[str, int]:
    stripped = text.lstrip()
    return stripped, start + (len(text) - len(stripped))


def _recursive_split(
    text: str,
    start_offset: int,
    chunk_size: int,
    overlap: int,
    separators: Optional[List[str]] = None,
) -> List[Tuple[str, int]]:
    if len(text) <= chunk_size:
        return [(text, start_offset)]

    separators = separators or _SEPARATORS
    separator: str = separators[-1]
    next_separators: List[str] = []
    for index, candidate in enumerate(separators):
        if candidate and candidate in text:
            separator = candidate
            next_separators = separators[index + 1 :]
            break

    if not separator:
        chunks: List[Tuple[str, int]] = []
        offset = 0
        while offset < len(text):
            chunk = text[offset : offset + chunk_size]
            chunks.append((chunk, start_offset + offset))
            offset += max(1, chunk_size - overlap)
        return chunks

    splits = text.split(separator)
    merged = _merge_splits(splits, separator, chunk_size, overlap)
    results: List[Tuple[str, int]] = []
    offset = 0
    for piece in merged:
        if len(piece) > chunk_size:
            results.extend(
                _recursive_split(piece, start_offset + offset, chunk_size, overlap, next_separators)
            )
        else:
            results.append((piece, start_offset + offset))
        offset += len(piece)
    return results


def _merge_splits(splits: List[str], separator: str, chunk_size: int, overlap: int) -> List[str]:
    merged: List[str] = []
    buffer = ""
    for split in splits:
        candidate = buffer + separator + split if buffer else split
        if len(candidate) > chunk_size and buffer:
            merged.append(buffer)
            buffer = buffer[-overlap:].lstrip() + separator + split if overlap else split
        else:
            buffer = candidate
    if buffer:
        merged.append(buffer)
    return merged


def _merge_small_chunks(pieces: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
    merged: List[Tuple[str, int]] = []
    for text, start_offset in pieces:
        if merged and len(text) < MIN_CHUNK_CHARS:
            previous_text, previous_offset = merged[-1]
            merged[-1] = (previous_text + _PAGE_SEPARATOR + text, previous_offset)
        else:
            merged.append((text, start_offset))
    return merged


def _page_for_offset(page_offsets: List[Tuple[int, int]], offset: int) -> int:
    page = page_offsets[0][1] if page_offsets else 1
    for start, page_number in page_offsets:
        if offset >= start:
            page = page_number
        else:
            break
    return page