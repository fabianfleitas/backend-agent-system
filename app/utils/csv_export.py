from __future__ import annotations

import csv
import io

from fastapi import Response


def to_csv(rows: list[dict], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for r in rows:
        writer.writerow([str(r.get(c) or "") for c in columns])
    return buf.getvalue()


def csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def metrics_to_csv(m) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["AGREGADOS", ""])
    for k, v in m.model_dump().items():
        if k in ("series", "tokens_by_model", "top_documents", "documents_by_category"):
            continue
        writer.writerow([k, v])
    writer.writerow([])
    writer.writerow(["TOKENS POR MODELO", "input", "output"])
    for modelo, t in (m.tokens_by_model or {}).items():
        writer.writerow([modelo, t.get("input"), t.get("output")])
    writer.writerow([])
    writer.writerow(["TOP DOCUMENTOS", "documento_id", "titulo", "consultas"])
    for d in m.top_documents:
        writer.writerow(["", d.documento_id, d.titulo, d.consultas])
    writer.writerow([])
    writer.writerow(["DISTRIBUCION POR CATEGORIA", "categoria_id", "nombre", "consultas"])
    for c in m.documents_by_category:
        writer.writerow(["", c.categoria_id, c.nombre, c.consultas])
    writer.writerow([])
    writer.writerow(["SERIE", "fecha", "conversaciones", "tokens_input", "tokens_output", "llm", "guard", "llm_failed"])
    for s in m.series:
        writer.writerow(["", s.fecha, s.conversaciones, s.tokens_input, s.tokens_output, s.llm, s.guard, s.llm_failed])
    return buf.getvalue()