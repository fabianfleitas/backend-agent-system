from __future__ import annotations

import os
from pathlib import Path


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def safe_join(base_dir: str, filename: str) -> str:
    base = Path(base_dir).resolve()
    candidate = (base / filename).resolve()
    if base not in candidate.parents and base != candidate:
        raise ValueError("unsafe_path")
    return str(candidate)


def write_bytes(path: str, data: bytes) -> None:
    parent = os.path.dirname(path)
    if parent:
        ensure_dir(parent)
    with open(path, "wb") as f:
        f.write(data)
