from __future__ import annotations

from typing import Optional

_token_encoder: Optional[object] = None


def count_tokens(text: str) -> int:
    global _token_encoder
    if _token_encoder is None:
        try:
            import tiktoken

            _token_encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            return max(1, len(text) // 4)
    return len(_token_encoder.encode(text))