#!/usr/bin/env python3
"""Evaluación del asistente contra el Gold Dataset (un comando).

Modo local (in-process, default):
    python3 -m eval.run_eval
  - Usa FastAPI TestClient y sobrescribe la auth con EVAL_USER_ID/EVAL_INSTITUCION_ID.
  - Autocrea una conversación (o usa EVAL_CONVERSATION_ID).
  - Lee los scores del judge (fidelidad/relevancia/contexto) desde audit_logs.
  - No requiere token (ejecuta en el host del backend).

Modo API real:
    EVAL_API_URL=http://localhost:8000 EVAL_AUTH_TOKEN=<jwt> python3 -m eval.run_eval
  - Requiere token válido; autocrea la conversación vía API si no se da EVAL_CONVERSATION_ID.
  - Los scores se leen de audit_logs solo si Supabase está configurado localmente.

Requiere la KB indexada (documentos READY) y `llm_enabled`/`judge_enabled` en true.
"""

from __future__ import annotations

import json
import os
import re
import sys
import csv
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import List, Optional, Sequence

import httpx

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "gold_dataset.json"
REPORTS = ROOT / "reports"

API_URL = os.environ.get("EVAL_API_URL", "").rstrip("/")
AUTH_TOKEN = os.environ.get("EVAL_AUTH_TOKEN", "")
CONVERSATION_ID: Optional[int] = None
try:
    CONVERSATION_ID = int(os.environ.get("EVAL_CONVERSATION_ID", "") or "")
except ValueError:
    CONVERSATION_ID = None
USER_ID = os.environ.get("EVAL_USER_ID", "eval-user")
INSTITUCION_ID = int(os.environ.get("EVAL_INSTITUCION_ID", "1"))
REUSE_CONVERSATION = os.environ.get(
    "EVAL_REUSE_CONVERSATION", "true" if CONVERSATION_ID is not None else "false"
).lower() in {
    "1", "true", "yes", "y", "on"
}
RATE_LIMIT_OVERRIDE = os.environ.get("EVAL_RATE_LIMIT_ENABLED")
RUN_LABEL = os.environ.get("EVAL_RUN_LABEL", "unlabeled")
EXTERNAL_PROVIDERS_APPROVED = os.environ.get(
    "EVAL_EXTERNAL_PROVIDERS_APPROVED", ""
).strip().lower() in {"1", "true", "yes", "y", "on"}
LIMIT: Optional[int] = None
try:
    LIMIT = int(os.environ.get("EVAL_LIMIT", "") or "")
except ValueError:
    LIMIT = None


def _load_dataset() -> List[dict]:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    return data["items"]


# ---------- cliente in-process (auth sobrescrita) ----------

def _build_local_client():
    from fastapi.testclient import TestClient
    from app.core.config import settings
    from app.core.security import AuthContext, get_auth_context
    from app.main import create_app

    if RATE_LIMIT_OVERRIDE is not None:
        settings.rate_limit_enabled = RATE_LIMIT_OVERRIDE.strip().lower() in {
            "1", "true", "yes", "y", "on"
        }

    app = create_app()

    def _override():
        return AuthContext(
            external_auth_id=USER_ID,
            institucion_id=INSTITUCION_ID,
            tipo_miembro="ESTUDIANTE",
            is_platform_admin=False,
        )

    app.dependency_overrides[get_auth_context] = _override
    return TestClient(app)


def _ensure_conversation(client) -> int:
    if CONVERSATION_ID is not None and REUSE_CONVERSATION:
        return CONVERSATION_ID
    resp = client.post("/api/conversations/")
    if resp.status_code != 201:
        raise RuntimeError(f"No se pudo crear la conversación: {resp.status_code} {resp.text[:200]}")
    return resp.json()["id"]


def _query(client, conversation_id: int, question: str) -> tuple[int, dict, float]:
    start = time.perf_counter()
    try:
        resp = client.post(
            "/api/chat/query",
            json={"conversation_id": conversation_id, "message": question},
        )
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return 0, {"error": f"{type(exc).__name__}: {exc}"}, elapsed_ms
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    if resp.status_code != 200:
        return resp.status_code, {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}, elapsed_ms
    return resp.status_code, resp.json(), elapsed_ms


# ---------- métricas ----------

def _normalize_title(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", without_marks))


def _fuente_encontrada(result: dict, fuentes_esperadas: str) -> bool:
    expected = _normalize_title(fuentes_esperadas or "")
    if not expected:
        return True
    return any(
        expected in _normalize_title(str(source.get("document") or ""))
        for source in (result.get("sources") or [])
    )


def _read_scores(audit_id: Optional[str]) -> Optional[dict]:
    """Lee scores del judge desde audit_logs (solo si Supabase está configurado)."""
    if not audit_id:
        return None
    try:
        from app.core.config import settings

        if not settings.supabase_configured:
            return None
        from app.repositories.audit_repository import AuditRepository

        row = AuditRepository().get_by_id(str(audit_id))
        if not row:
            return None
        return {
            "fidelidad": row.get("score_fidelidad"),
            "relevancia": row.get("score_relevancia"),
            "contexto": row.get("score_contexto"),
            "observaciones": row.get("observaciones") or "",
        }
    except Exception:  # noqa: BLE001
        return None


def _avg(values: List[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 4)


def _percentile(values: Sequence[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int((percentile / 100.0) * len(ordered) + 0.999999))
    return ordered[min(rank - 1, len(ordered) - 1)]


def _resolved_judge_setting() -> Optional[bool]:
    try:
        from app.core.config import settings
        from app.services.config_service import ConfigService

        return ConfigService().get_bool(
            "judge_enabled", INSTITUCION_ID, settings.judge_enabled
        )
    except Exception:  # noqa: BLE001 - evaluation must retain results if config lookup fails
        return None


def _resolved_llm_setting() -> Optional[bool]:
    try:
        from app.core.config import settings
        from app.services.config_service import ConfigService

        return ConfigService().get_bool("llm_enabled", INSTITUCION_ID, settings.llm_enabled)
    except Exception:  # noqa: BLE001
        return None


def _resolved_llm_model() -> Optional[str]:
    try:
        from app.core.config import settings
        from app.services.config_service import ConfigService

        return ConfigService().get_str("llm_model", INSTITUCION_ID, settings.llm_model)
    except Exception:  # noqa: BLE001
        return None


def _resolved_rate_limit_setting() -> Optional[bool]:
    try:
        from app.core.config import settings

        return bool(settings.rate_limit_enabled)
    except Exception:  # noqa: BLE001
        return None


def _write_human_review_template(rows: List[dict]) -> Path:
    """Write a blinded-review worksheet; annotations are intentionally left blank."""
    out = REPORTS / f"human_review_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.csv"
    fields = [
        "id",
        "pregunta",
        "respuesta_esperada",
        "respuesta_generada",
        "fuente_esperada",
        "fuentes_recuperadas",
        "fuente_esperada_encontrada",
        "correcta_revisor",
        "fiel_a_fuente_revisor",
        "cita_sustentada_revisor",
        "observaciones_revisor",
    ]
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": row.get("id"),
                    "pregunta": row.get("pregunta"),
                    "respuesta_esperada": row.get("respuesta_esperada"),
                    "respuesta_generada": row.get("respuesta"),
                    "fuente_esperada": row.get("fuente_esperada"),
                    "fuentes_recuperadas": " | ".join(row.get("fuentes") or []),
                    "fuente_esperada_encontrada": row.get("fuente_esperada_encontrada"),
                    "correcta_revisor": "",
                    "fiel_a_fuente_revisor": "",
                    "cita_sustentada_revisor": "",
                    "observaciones_revisor": "",
                }
            )
    return out


def main() -> int:
    if not EXTERNAL_PROVIDERS_APPROVED:
        print(
            "Se requiere EVAL_EXTERNAL_PROVIDERS_APPROVED=true para autorizar "
            "llamadas externas de LLM/embeddings/juez."
        )
        return 2

    from app.core.config import settings

    items = _load_dataset()
    if LIMIT is not None:
        items = items[:LIMIT]
    REPORTS.mkdir(parents=True, exist_ok=True)

    http_mode = bool(API_URL)
    if http_mode and not AUTH_TOKEN:
        raise SystemExit("EVAL_AUTH_TOKEN es obligatorio al usar EVAL_API_URL")

    if http_mode:
        client = httpx.Client(
            base_url=API_URL,
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
            timeout=90.0,
        )
    else:
        client = _build_local_client()

    rows: List[dict] = []
    status_counts: dict[str, int] = {}
    source_hits = 0
    errors = 0
    fidelidades: List[Optional[float]] = []
    relevancias: List[Optional[float]] = []
    contextos: List[Optional[float]] = []
    latencies_ms: List[float] = []
    successful_latencies_ms: List[float] = []
    conversation_ids: List[int] = []
    judge_status_counts: dict[str, int] = {}

    try:
        with client:
            if REUSE_CONVERSATION and CONVERSATION_ID is not None:
                conversation_ids = [CONVERSATION_ID] * len(items)
            else:
                # An isolated conversation per query prevents the previous Gold
                # items from leaking into the enabled conversational history.
                conversation_ids = [
                    _ensure_conversation(client) for _ in items
                ]

            judge_enabled = _resolved_judge_setting() if not http_mode else None
            for item, conversation_id in zip(items, conversation_ids):
                question = item["pregunta"]
                try:
                    status_code, result, elapsed_ms = _query(client, conversation_id, question)
                    status_key = str(status_code)
                except Exception as exc:  # noqa: BLE001
                    status_code = 0
                    result = {"error": f"{type(exc).__name__}: {exc}"}
                    elapsed_ms = 0.0
                    status_key = "exception"
                status_counts[status_key] = status_counts.get(status_key, 0) + 1
                latencies_ms.append(elapsed_ms)

                if status_code != 200 or not result or result.get("error"):
                    errors += 1
                    rows.append(
                        {
                            "id": item["id"],
                            "pregunta": question,
                            "respuesta_esperada": item.get("respuesta_esperada", ""),
                            "fuente_esperada": item.get("fuente_esperada", ""),
                            "estado": "error",
                            "http_status": status_code,
                            "latencia_ms": round(elapsed_ms, 1),
                            "detalle": result.get("error"),
                        }
                    )
                    continue

                successful_latencies_ms.append(elapsed_ms)

                source_hit = _fuente_encontrada(result, item.get("fuente_esperada", ""))
                if source_hit:
                    source_hits += 1
                scores = _read_scores(result.get("audit_id"))
                if scores:
                    fidelidades.append(scores["fidelidad"])
                    relevancias.append(scores["relevancia"])
                    contextos.append(scores["contexto"])
                    observations = scores.get("observaciones", "")
                    if "JUDGE:ok" in observations:
                        judge_status = "ok"
                    elif "JUDGE_FAILED" in observations:
                        judge_status = "failed"
                    else:
                        judge_status = "no_score_or_disabled"
                    judge_status_counts[judge_status] = judge_status_counts.get(judge_status, 0) + 1
                rows.append(
                    {
                        "id": item["id"],
                        "pregunta": question,
                        "respuesta_esperada": item.get("respuesta_esperada", ""),
                        "estado": "ok",
                        "http_status": status_code,
                        "latencia_ms": round(elapsed_ms, 1),
                        "fuente_esperada": item.get("fuente_esperada", ""),
                        "fuente_esperada_encontrada": source_hit,
                        "fuentes": [s.get("document") for s in (result.get("sources") or [])],
                        "scores_judge": {
                            key: scores.get(key)
                            for key in ("fidelidad", "relevancia", "contexto")
                        } if scores else None,
                        "judge_status": judge_status if scores else "audit_score_unavailable",
                        "revision_humana": "pendiente",
                        "respuesta": result.get("response") or "",
                        "audit_id": result.get("audit_id"),
                    }
                )
    finally:
        client.close()

    total = len(items)
    report = {
        "fecha": datetime.now().isoformat(),
        "run_label": RUN_LABEL,
        "modo": "api" if http_mode else "local",
        "configuracion": {
            "llm_enabled_resuelto_local": _resolved_llm_setting() if not http_mode else None,
            "judge_enabled_resuelto_local": judge_enabled if not http_mode else None,
            "embeddings_enabled": settings.embeddings_enabled,
            "embedding_model": settings.embedding_model,
            "llm_model_resuelto_local": _resolved_llm_model() if not http_mode else None,
            "conversation_reused": REUSE_CONVERSATION and CONVERSATION_ID is not None,
            "rate_limit_override": RATE_LIMIT_OVERRIDE if not http_mode else None,
            "rate_limit_enabled_local": _resolved_rate_limit_setting() if not http_mode else None,
        },
        "total": total,
        "source_hits": source_hits,
        "source_hit_rate": round(source_hits / total, 4) if total else 0.0,
        "source_hit_definition": (
            "Coincidencia del título de la fuente esperada completa, normalizada, "
            "con un título recuperado. No mide la corrección de la respuesta."
        ),
        "answer_correctness_assessed": False,
        "judge_scores": {
            "fidelidad_avg": _avg(fidelidades),
            "relevancia_avg": _avg(relevancias),
            "contexto_avg": _avg(contextos),
            "evaluadas_con_scores": sum(1 for value in fidelidades if value is not None),
            "estado_observado": judge_status_counts,
        },
        "latencia_ms": {
            "solicitudes_totales": len(latencies_ms),
            "solicitudes_exitosas": len(successful_latencies_ms),
            "p50_exitosas": round(median(successful_latencies_ms), 1) if successful_latencies_ms else None,
            "p95_exitosas": (
                round(_percentile(successful_latencies_ms, 95), 1)
                if len(successful_latencies_ms) >= 100
                else None
            ),
            "p95_status": (
                "reportado"
                if len(successful_latencies_ms) >= 100
                else "no representativo: menos de 100 respuestas exitosas"
            ),
            "max_exitosas": round(max(successful_latencies_ms), 1) if successful_latencies_ms else None,
        },
        "http_status_counts": status_counts,
        "errores": errors,
        "items": rows,
    }
    out = REPORTS / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    review_out = _write_human_review_template(rows)

    print(f"Reporte: {out}")
    print(f"Planilla de revisión humana: {review_out}")
    print(
        f"Modo={report['modo']} | juez configuración local={judge_enabled} "
        f"| estado observado={judge_status_counts}"
    )
    print(
        f"Total={total} | fuentes esperadas recuperadas={source_hits} "
        f"({report['source_hit_rate']:.1%}) | Errores={errors} | HTTP={status_counts}"
    )
    if report["judge_scores"]["evaluadas_con_scores"]:
        js = report["judge_scores"]
        print(
            f"Judge ({js['evaluadas_con_scores']} evaluadas): fidelidad={js['fidelidad_avg']} "
            f"relevancia={js['relevancia_avg']} contexto={js['contexto_avg']}"
        )
    else:
        print("Judge: sin scores (verificar judge_enabled=true y llm_enabled=true).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
