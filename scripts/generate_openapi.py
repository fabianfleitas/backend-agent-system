#!/usr/bin/env python3
"""Regenerar openapi.current.json desde create_app(). Modo --check compara con archivo existente."""
from __future__ import annotations

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import create_app

OUTPUT = Path(__file__).resolve().parent.parent / "openapi.current.json"


def main() -> int:
    check = "--check" in sys.argv
    app = create_app()
    schema = app.openapi()
    content = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True)
    if check:
        current = OUTPUT.read_text(encoding="utf-8")
        if content == current:
            print("openapi.current.json is up to date.")
            return 0
        else:
            # Escribir a temp para comparar fácilmente
            temp = Path("/tmp/openapi_new.json")
            temp.write_text(content, encoding="utf-8")
            print(f"FAIL: openapi.current.json differs from current schema.")
            print(f"  Current: {len(current)} chars")
            print(f"  New: {len(content)} chars")
            print(f"  Diff temp: {temp}")
            return 1
    else:
        OUTPUT.write_text(content, encoding="utf-8")
        print(f"Wrote {OUTPUT} ({len(content)} chars)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
