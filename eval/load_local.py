#!/usr/bin/env python3
"""Mide una línea base secuencial del endpoint chat en proceso.

Este script NO es una prueba de concurrencia: usa un TestClient en un solo hilo,
crea una conversación independiente por consulta y registra códigos HTTP. Para
concurrencia y capacidad HTTP se debe usar eval/k6_load.js contra un despliegue
de pruebas.

La regla de rate limit se conserva por defecto. Para aislar la latencia del
pipeline en una ejecución local, se puede pasar EVAL_RATE_LIMIT_ENABLED=false;
el reporte registra ese override y no debe interpretarse como el comportamiento
del servicio con el rate limit activo.

Uso:
    EVAL_MAX_REQUESTS=100 python3 -m eval.load_local
    EVAL_RATE_LIMIT_ENABLED=false EVAL_MAX_REQUESTS=100 python3 -m eval.load_local
"""

from __future__ import annotations

import json
import os
import resource
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import List, Optional, Sequence

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "gold_dataset.json"
REPORTS = ROOT / "reports"

MAX_REQUESTS = int(os.environ.get("EVAL_MAX_REQUESTS", "100"))
INTER_REQUEST_DELAY_S = float(os.environ.get("EVAL_INTERVAL_S", "0"))
USER_ID = os.environ.get("EVAL_USER_ID", "eval-user")
INSTITUCION_ID = int(os.environ.get("EVAL_INSTITUCION_ID", "1"))
RATE_LIMIT_OVERRIDE = os.environ.get("EVAL_RATE_LIMIT_ENABLED")


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _questions() -> List[str]:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    return [i["pregunta"] for i in data["items"]]


def _client():
    from fastapi.testclient import TestClient
    from app.core.config import settings
    from app.core.security import AuthContext, get_auth_context
    from app.main import create_app

    if RATE_LIMIT_OVERRIDE is not None:
        settings.rate_limit_enabled = _parse_bool(RATE_LIMIT_OVERRIDE)

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


def _percentile(values: Sequence[float], percentile: float) -> Optional[float]:
    """Nearest-rank percentile; callers decide whether n is sufficient to report it."""
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
    except Exception:  # noqa: BLE001 - the report must still be written on config-read failure
        return None


def main() -> int:
    if MAX_REQUESTS < 1:
        raise SystemExit("EVAL_MAX_REQUESTS debe ser >= 1")
    if INTER_REQUEST_DELAY_S < 0:
        raise SystemExit("EVAL_INTERVAL_S no puede ser negativo")

    questions = _questions()
    from app.core.config import settings

    judge_enabled = _resolved_judge_setting()
    client = _client()
    status_counts: Counter[str] = Counter()
    successful_latencies: List[float] = []
    all_latencies: List[float] = []
    exceptions = 0

    try:
        # Prepare isolated conversations before timing the chat endpoint.
        conversation_ids: List[int] = []
        for _ in range(MAX_REQUESTS):
            response = client.post("/api/conversations/")
            if response.status_code != 201:
                raise RuntimeError(
                    "No se pudo crear una conversación de prueba: "
                    f"HTTP {response.status_code} {response.text[:200]}"
                )
            conversation_ids.append(int(response.json()["id"]))

        start = time.perf_counter()
        cpu0 = os.times()
        for index, conversation_id in enumerate(conversation_ids):
            question = questions[index % len(questions)]
            request_start = time.perf_counter()
            try:
                response = client.post(
                    "/api/chat/query",
                    json={"conversation_id": conversation_id, "message": question},
                )
                code = response.status_code
                status_counts[str(code)] += 1
                elapsed_ms = (time.perf_counter() - request_start) * 1000.0
                all_latencies.append(elapsed_ms)
                if code == 200:
                    successful_latencies.append(elapsed_ms)
            except Exception as exc:  # noqa: BLE001
                exceptions += 1
                status_counts["exception"] += 1
                all_latencies.append((time.perf_counter() - request_start) * 1000.0)
                print(f"Excepción en solicitud {index + 1}: {type(exc).__name__}")
            if INTER_REQUEST_DELAY_S:
                time.sleep(INTER_REQUEST_DELAY_S)
        wall = time.perf_counter() - start
        cpu1 = os.times()
    finally:
        client.close()

    attempts = len(all_latencies)
    successes = len(successful_latencies)
    errors = attempts - successes
    cpu_percent = (
        ((cpu1.user - cpu0.user) + (cpu1.system - cpu0.system)) / wall * 100.0
        if wall > 0
        else 0.0
    )
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes (macOS) / KB (Linux)
    rss_mb = rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024
    p95_success = _percentile(successful_latencies, 95) if successes >= 100 else None
    p99_success = _percentile(successful_latencies, 99) if successes >= 100 else None

    report = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "tipo_prueba": "linea_base_local_secuencial_in_process",
        "nota": "No es una prueba de concurrencia ni representa un despliegue de producción.",
        "vus": 1,
        "duracion_s": round(wall, 2),
        "requests": attempts,
        "solicitudes_exitosas": successes,
        "solicitudes_fallidas": errors,
        "excepciones": exceptions,
        "codigos_http": dict(status_counts),
        "rps_total": round(attempts / wall, 3) if wall > 0 else 0.0,
        "rps_exitosas": round(successes / wall, 3) if wall > 0 else 0.0,
        "error_rate": round(errors / attempts, 4) if attempts else 0.0,
        "latencia_exitosa_ms": {
            "n": successes,
            "p50": round(median(successful_latencies), 1) if successful_latencies else None,
            "p95": round(p95_success, 1) if p95_success is not None else None,
            "p99": round(p99_success, 1) if p99_success is not None else None,
            "max": round(max(successful_latencies), 1) if successful_latencies else None,
        },
        "latencia_todas_ms": {
            "n": attempts,
            "p50": round(median(all_latencies), 1) if all_latencies else None,
            "p95": round(_percentile(all_latencies, 95), 1) if attempts >= 100 else None,
            "max": round(max(all_latencies), 1) if all_latencies else None,
        },
        "configuracion": {
            "llm_enabled": settings.llm_enabled,
            "embeddings_enabled": settings.embeddings_enabled,
            "judge_enabled_resuelto": judge_enabled,
            "rate_limit_enabled": settings.rate_limit_enabled,
            "rate_limit_override": RATE_LIMIT_OVERRIDE,
            "inter_request_delay_s": INTER_REQUEST_DELAY_S,
        },
        "cpu_percent": round(cpu_percent, 1),
        "ram_max_mb": round(rss_mb, 1),
        "p95_estado": (
            "estimable_con_100_o_mas_respuestas_exitosas"
            if p95_success is not None
            else "no_reportado: se requieren al menos 100 respuestas exitosas"
        ),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"load_local_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Reporte: {out}")
    print(
        f"Secuencial local | duración={wall:.1f}s | solicitudes={attempts} "
        f"| exitosas={successes} | fallidas={errors} ({report['error_rate']:.2%}) "
        f"| códigos={dict(status_counts)}"
    )
    print(
        "Latencia exitosa ms: "
        f"n={successes} p50={report['latencia_exitosa_ms']['p50']} "
        f"p95={report['latencia_exitosa_ms']['p95']} "
        f"p99={report['latencia_exitosa_ms']['p99']}"
    )
    print(f"CPU={cpu_percent:.1f}% | RAM máx={rss_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
