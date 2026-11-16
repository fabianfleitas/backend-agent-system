#!/usr/bin/env python3
"""Backup diario de la base de datos (RNF-06) con retención de 7 días.

Usa `pg_dump` contra `DATABASE_URL` (connection string de Supabase/Postgres).

Uso:
    DATABASE_URL=postgresql://... python3 scripts/backup_db.py
    BACKUP_DIR=backups BACKUP_RETENTION_DAYS=7 python3 scripts/backup_db.py

Salida: `backups/<fecha>_<hora>.sql` (plain). Elimina backups más antiguos que
la retención.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "")
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "backups"))
RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "7"))
BACKUP_OPTS = os.environ.get("BACKUP_OPTS", "--no-owner --no-privileges --format=plain")


def _run_backup(database_url: str, dest: Path) -> None:
    cmd = ["pg_dump", *BACKUP_OPTS.split(), "--dbname", database_url, "--file", str(dest)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump falló ({result.returncode}): {result.stderr[-2000:]}")


def _prune(retention_days: int) -> None:
    cutoff = datetime.now() - timedelta(days=retention_days)
    for f in BACKUP_DIR.glob("*.sql"):
        try:
            ts = datetime.fromtimestamp(f.stat().st_mtime)
        except OSError:
            continue
        if ts < cutoff:
            f.unlink()
            print(f"Eliminado (retención {retention_days}d): {f.name}")


def main() -> int:
    if not DATABASE_URL:
        print(
            "ERROR: falta DATABASE_URL (connection string de Postgres). "
            "Ej.: postgresql://postgres.xxxx:pass@aws-0-region.pooler.supabase.com:6543/postgres",
            file=sys.stderr,
        )
        return 1
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    try:
        _run_backup(DATABASE_URL, dest)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Backup OK: {dest} ({dest.stat().st_size} bytes)")
    _prune(RETENTION_DAYS)
    return 0


if __name__ == "__main__":
    sys.exit(main())