#!/usr/bin/env python3
"""Marca como EXPIRED las suscripciones con fecha_vencimiento pasada y notifica.

Uso:
  python scripts/check_subscription_expiry.py            # ejecuta
  python scripts/check_subscription_expiry.py --dry-run  # solo reporta

No requiere Celery/Redis; pensado para ejecutarse manualmente o vía cron.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.repositories.billing_repository import BillingRepository
from app.repositories.notifications_repository import NotificationsRepository
from app.repositories.institutions_repository import InstitutionsRepository
from app.services.notification_service import NotificationService

ACTIVE_STATES = ("ACTIVE", "TRIAL", "PENDING_PAYMENT")


def _expired(sub) -> bool:
    fecha = sub.get("fecha_vencimiento")
    if not fecha:
        return False
    try:
        return datetime.fromisoformat(str(fecha).replace("Z", "+00:00")) < datetime.now(timezone.utc)
    except Exception:
        return False


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    billing_repo = BillingRepository()
    notifications_service = NotificationService(notifications_repo=NotificationsRepository())
    institutions_repo = InstitutionsRepository()

    expired = [
        s for s in billing_repo.list_subscriptions()
        if s.get("estado") in ACTIVE_STATES and _expired(s)
    ]
    if not expired:
        print("No hay suscripciones vencidas.")
        return 0

    print(f"Encontradas {len(expired)} suscripciones vencidas:")
    for sub in expired:
        print(f"  - #{sub.get('id')} inst={sub.get('institucion_id')} estado={sub.get('estado')} vence={sub.get('fecha_vencimiento')}")
        if dry_run:
            continue
        try:
            billing_repo.update_subscription_stripe_refs(sub["id"], estado="EXPIRED")
            billing_repo.create_suscripcion_historial(
                suscripcion_id=sub["id"],
                tipo_evento="SUBSCRIPTION_UPDATED",
                estado_anterior=sub.get("estado"),
                estado_nuevo="EXPIRED",
                descripcion="Expiración automática por fecha de vencimiento",
            )
            institution = institutions_repo.get_institucion(sub.get("institucion_id"))
            destinatario = (institution or {}).get("email_contacto")
            if destinatario:
                notifications_service.send_automated(
                    sub.get("institucion_id"),
                    destinatario=destinatario,
                    asunto="Suscripción expirada",
                    contenido="Tu suscripción alcanzó su fecha de vencimiento.",
                    contenido_texto="Tu suscripción alcanzó su fecha de vencimiento.",
                    tipo="SUBSCRIPTION_EXPIRED",
                    suscripcion_id=sub["id"],
                    clave_idempotencia=f"expiry-{sub['id']}",
                )
            print(f"    -> marcada EXPIRED")
        except Exception as exc:  # noqa: BLE001
            print(f"    -> error: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())