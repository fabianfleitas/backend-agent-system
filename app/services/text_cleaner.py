from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\ufeff"
_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_TYPOGRAPHIC_QUOTES = str.maketrans(
    {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u00ab": '"',
        "\u00bb": '"',
    }
)


def clean_page_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_CHARS_PATTERN.sub("", text)
    text = text.translate(str.maketrans("", "", _ZERO_WIDTH_CHARS)).translate(_TYPOGRAPHIC_QUOTES)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def normalize_for_dedup(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", "", decomposed).lower()