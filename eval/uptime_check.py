#!/usr/bin/env python3
"""Probe de disponibilidad (RNF-05) contra /ready del backend (in-process).

Consulta /ready (público) cada EVAL_UPTIME_INTERVAL durante EVAL_UPTIME_SECONDS
y reporta el uptime %. Es un smoke local; el uptime real requiere el despliegue
y monitoreo del entorno (S13).

Uso:
    python3 -m eval.uptime_check
    EVAL_UPTIME_SECONDS=60 EVAL_UPTIME_INTERVAL=2 python3 -m eval.uptime_check
"""

from __future__ import annotations

import os
import sys
import time

SECONDS = int(os.environ.get("EVAL_UPTIME_SECONDS", "30"))
INTERVAL = int(os.environ.get("EVAL_UPTIME_INTERVAL", "1"))


def main() -> int:
    from fastapi.testclient import TestClient
    from app.main import create_app

    client = TestClient(create_app())
    ok = 0
    total = 0
    start = time.perf_counter()
    while time.perf_counter() - start < SECONDS:
        try:
            resp = client.get("/ready")
            body = resp.json()
            if resp.status_code == 200 and body.get("status") == "ready":
                ok += 1
        except Exception:  # noqa: BLE001
            pass
        total += 1
        time.sleep(INTERVAL)

    uptime = ok / total if total else 0.0
    print(f"Probes={total} | ok={ok} | uptime={uptime:.1%} | ventana={SECONDS}s")
    print(f"Criterio: uptime >= 95% mensual (requiere deploy para medición real).")
    return 0


if __name__ == "__main__":
    sys.exit(main())