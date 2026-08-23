from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import fitz

logger = logging.getLogger(__name__)


@dataclass
class PdfPageText:
    page_number: int
    text: str
    char_count: int


@dataclass
class PdfExtractionResult:
    page_count: int
    pages: List[PdfPageText] = field(default_factory=list)
    total_chars: int = 0
    ok: bool = True
    error: Optional[str] = None


def extract_text_from_pdf(file_bytes: bytes) -> PdfExtractionResult:
    result = PdfExtractionResult(page_count=0)
    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
        result.page_count = document.page_count
        for page in document:
            text = page.get_text("text")
            page_text = PdfPageText(
                page_number=page.number + 1,
                text=text,
                char_count=len(text),
            )
            result.pages.append(page_text)
            result.total_chars += len(text)
        document.close()
    except (RuntimeError, ValueError) as exc:
        result.ok = False
        result.error = str(exc)
        result.pages = []
        result.total_chars = 0
    return result