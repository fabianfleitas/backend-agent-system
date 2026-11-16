#!/usr/bin/env python3
"""Ejecuta k6_sustained.js y muestrea CPU/RSS del backend local.

Uso:
    python -m eval.run_sustained_local \
      --token-file /ruta/segura/local_test.jwt \
      --backend-pid <pid> \
      --vus 8 --iterations-per-vu 30 --sleep 1

No imprime el JWT. Los procesos externos y el backend deben estar levantados
manualmente; este script solo orquesta k6 y toma muestras de `ps`.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "eval" / "reports"


def _sample_process(pid: int) -> tuple[float, float] | None:
    try:
        output = subprocess.check_output(
            ["ps", "-o", "%cpu=,rss=", "-p", str(pid)],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if not output:
        return None
    parts = output.split()
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1]) / 1024.0
    except ValueError:
        return None


def _summarize(samples: list[tuple[float, float]]) -> dict:
    if not samples:
        return {"muestras": 0}
    cpu = [s[0] for s in samples]
    rss = [s[1] for s in samples]
    return {
        "muestras": len(samples),
        "cpu_percent_promedio_ps": round(statistics.mean(cpu), 2),
        "cpu_percent_max_ps": round(max(cpu), 2),
        "rss_mb_max": round(max(rss), 1),
        "rss_mb_promedio": round(statistics.mean(rss), 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8001")
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--backend-pid", type=int, required=True)
    parser.add_argument("--vus", type=int, default=8)
    parser.add_argument("--iterations-per-vu", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--summary-out", default="")
    parser.add_argument("--raw-out", default="")
    parser.add_argument("--result-out", default="")
    args = parser.parse_args()

    token_path = Path(args.token_file)
    if not token_path.exists():
        print(f"No existe el archivo de token: {token_path}")
        return 2
    token = token_path.read_text(encoding="utf-8").strip()
    if not token:
        print("El archivo de token está vacío")
        return 2
    if not args.api_url.startswith(("http://127.0.0.1", "http://localhost")):
        print("Este runner solo acepta API local (127.0.0.1/localhost)")
        return 2
    if _sample_process(args.backend_pid) is None:
        print("No se pudo leer el proceso del backend indicado")
        return 2

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    summary_path = Path(args.summary_out or REPORTS / f"k6_sustained_{stamp}.json")
    raw_path = Path(args.raw_out or REPORTS / f"k6_sustained_{stamp}_raw.json")
    result_path = Path(args.result_out or REPORTS / f"k6_sustained_{stamp}_result.json")
    for path in (summary_path, raw_path, result_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "EVAL_API_URL": args.api_url,
            "EVAL_TOKEN": token,
            "EVAL_VUS": str(args.vus),
            "EVAL_ITERATIONS_PER_VU": str(args.iterations_per_vu),
            "EVAL_SLEEP_S": str(args.sleep),
        }
    )

    samples: list[tuple[float, float]] = []
    stop = threading.Event()

    def sampler() -> None:
        while not stop.is_set():
            sample = _sample_process(args.backend_pid)
            if sample is not None:
                samples.append(sample)
            stop.wait(args.interval)

    thread = threading.Thread(target=sampler, daemon=True)
    started = datetime.now(timezone.utc)
    thread.start()
    try:
        completed = subprocess.run(
            [
                "k6",
                "run",
                "--summary-export",
                str(summary_path),
                "--out",
                f"json={raw_path}",
                str(ROOT / "eval" / "k6_sustained.js"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        stop.set()
        thread.join(timeout=5)

    result = {
        "fecha": started.isoformat(),
        "tipo": "carga_sostenida_local_sintetica",
        "api_url": args.api_url,
        "vus": args.vus,
        "iterations_per_vu": args.iterations_per_vu,
        "sleep_s": args.sleep,
        "requested_chat_requests": args.vus * args.iterations_per_vu,
        "k6_exit_code": completed.returncode,
        "k6_stdout": completed.stdout[-6000:],
        "k6_stderr": completed.stderr[-3000:],
        "server_process_samples": _summarize(samples),
        "summary_report": str(summary_path),
        "raw_report": str(raw_path),
        "advertencia": (
            "Carga local sintética. No representa proveedores externos, "
            "producción ni el SLO de 3 s."
        ),
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(completed.stdout)
    print(f"Reporte de ejecución: {result_path}")
    return 0 if completed.returncode == 0 else completed.returncode


if __name__ == "__main__":
    sys.exit(main())
