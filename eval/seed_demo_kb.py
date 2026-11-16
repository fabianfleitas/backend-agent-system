#!/usr/bin/env python3
"""Carga la Knowledge Base de prueba (S12) con documentación sintética.

Genera un PDF por documento de `eval/demo_kb.json` (PyMuPDF) y lo sube por el
endpoint real `POST /api/admin/documents` (TestClient + auth sobrescrita ADMIN,
institución 1). Idempotente por `codigo_documento` (DEMO-*).

Uso:
    python3 -m eval.seed_demo_kb              # carga + indexa
    python3 -m eval.seed_demo_kb --deactivate # soft-disable de documentos DEMO-*
    python3 -m eval.seed_demo_kb --dry-run    # muestra qué cargaría sin subir
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent
DEMO_KB = ROOT / "demo_kb.json"
INSTITUCION_ID = 1
ADMIN_EID = "seed-admin"


def _external_providers_approved() -> bool:
    return os.environ.get("EVAL_EXTERNAL_PROVIDERS_APPROVED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _wrap(text: str, width: int = 95) -> List[str]:
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        if not cur or len(cur) + 1 + len(w) <= width:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _make_pdf(titulo: str, parrafos: List[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), titulo, fontsize=14)
    y = 100
    for par in parrafos:
        for line in _wrap(par):
            page.insert_text((72, y), line, fontsize=10)
            y += 14
            if y > 750:
                page = doc.new_page()
                y = 72
    return doc.tobytes()


def _load() -> List[dict]:
    return json.loads(DEMO_KB.read_text(encoding="utf-8"))["documentos"]


def _client():
    from fastapi.testclient import TestClient
    from app.core.security import AuthContext, get_auth_context
    from app.main import create_app

    app = create_app()

    def _override():
        return AuthContext(
            external_auth_id=ADMIN_EID,
            institucion_id=INSTITUCION_ID,
            tipo_miembro="ADMIN",
            is_platform_admin=False,
        )

    app.dependency_overrides[get_auth_context] = _override
    return TestClient(app)


def _existing_codigos(client) -> set:
    resp = client.get("/api/admin/documents?limit=100&offset=0")
    if resp.status_code != 200:
        return set()
    items = resp.json().get("items", [])
    return {i.get("codigo_documento") for i in items if i.get("codigo_documento")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed KB demo")
    parser.add_argument("--deactivate", action="store_true", help="Soft-disable documentos DEMO-*")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué haría")
    args = parser.parse_args()

    client = _client()

    if args.deactivate:
        resp = client.get("/api/admin/documents?limit=100&offset=0")
        items = resp.json().get("items", [])
        demo = [i for i in items if (i.get("codigo_documento") or "").startswith("DEMO-")]
        for i in demo:
            if args.dry_run:
                print(f"[dry] Desactivaría documento {i['id']} {i.get('codigo_documento')}")
                continue
            r = client.delete(f"/api/admin/documents/{i['id']}")
            print(f"Desactivado {i.get('codigo_documento')} id={i['id']} -> {r.status_code}")
        print(f"Totales: {len(demo)} documentos demo.")
        return 0

    if not _external_providers_approved():
        print(
            "Se requiere EVAL_EXTERNAL_PROVIDERS_APPROVED=true para indexar con "
            "embeddings externos. Usa --dry-run para revisar sin llamadas."
        )
        return 2

    documentos = _load()
    existing = _existing_codigos(client)
    creados = 0
    for doc in documentos:
        codigo = doc["codigo"]
        if codigo in existing:
            print(f"Ya existe {codigo}: {doc['titulo']} (omitido)")
            continue
        if args.dry_run:
            print(f"[dry] Subiría {codigo}: {doc['titulo']} ({len(doc['parrafos'])} párrafos)")
            continue
        pdf = _make_pdf(doc["titulo"], doc["parrafos"])
        resp = client.post(
            "/api/admin/documents",
            data={
                "titulo": doc["titulo"],
                "codigo_documento": codigo,
                "descripcion": "Documentación sintética de prueba (S12)",
            },
            files={"file": (f"{codigo}.pdf", pdf, "application/pdf")},
        )
        if resp.status_code not in (200, 201):
            print(f"ERROR {codigo}: {resp.status_code} {resp.text[:200]}")
            continue
        body = resp.json()
        creados += 1
        print(f"OK {codigo}: {doc['titulo']} -> doc={body['document']['id']} ver={body['version']['id']} status={body['version']['status']}")

    print(f"\nCreados: {creados}/{len(documentos)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())