#!/usr/bin/env python3
"""Reprocesa eventos Stripe que quedaron sin procesar o fallidos.

Uso:
  python scripts/reprocess_stripe_events.py            # reprocesa todos los no procesados
  python scripts/reprocess_stripe_events.py --dry-run  # solo lista

Stripe ya reintenta la entrega ante 500; este script cubre eventos persistidos
en `stripe_eventos` que fallaron y quedaron `procesado=false`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.supabase import get_supabase_client
from app.services.stripe_webhook_service import StripeWebhookService


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    client = get_supabase_client()
    resp = (
        client.table("stripe_eventos")
        .select("stripe_event_id, tipo_evento, payload")
        .eq("procesado", False)
        .execute()
    )
    events = list(resp.data or [])
    if not events:
        print("No hay eventos sin procesar.")
        return 0

    print(f"Encontrados {len(events)} eventos sin procesar:")
    service = StripeWebhookService()
    for ev in events:
        print(f"  - {ev.get('tipo_evento')} {ev.get('stripe_event_id')}")
        if dry_run:
            continue
        try:
            result = service.handle_event(ev.get("payload") or {})
            print(f"    -> {result.get('status')}")
        except Exception as exc:  # noqa: BLE001
            print(f"    -> error: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())