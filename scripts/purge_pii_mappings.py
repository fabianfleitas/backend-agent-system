#!/usr/bin/env python3
"""Purgar mappings PII vencidos (TTL) de la tabla pii_mappings.

Uso:
    python3 scripts/purge_pii_mappings.py              # purga vencidos ahora
    python3 scripts/purge_pii_mappings.py --days 30    # cutoff = now - 30d
    python3 scripts/purge_pii_mappings.py --dry-run    # solo reporta, no borra

El vencimiento lo definen los registros (expires_at <= cutoff). La política
de retención por defecto se toma de PII_MAPPING_RETENTION_DAYS (settings).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.repositories.pii_repository import PiiRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Expirar mappings con expires_at <= (now - days). Default: PII_MAPPING_RETENTION_DAYS.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo listar los vencidos sin borrar.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repository = PiiRepository()

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days) if args.days else datetime.now(timezone.utc)
    expired = repository.list_expired(before=cutoff)
    print(f"Expired mappings: {len(expired)} (cutoff={cutoff.isoformat()})")

    if args.dry_run or not expired:
        return 0

    deleted = repository.purge_expired(before=cutoff)
    print(f"Purged mappings: {deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
