from __future__ import annotations

from typing import Any, Optional

from app.repositories.billing_repository import BillingRepository
from app.repositories.stripe_events_repository import StripeEventsRepository


class StripeWebhookService:
    def __init__(
        self,
        events_repo: Optional[StripeEventsRepository] = None,
        billing_repo: Optional[BillingRepository] = None,
    ) -> None:
        self.events_repo = events_repo or StripeEventsRepository()
        self.billing_repo = billing_repo or BillingRepository()

    def register_event(self, stripe_event_id: str, event_type: str, payload: dict[str, Any]) -> dict:
        existing = self.events_repo.get_event(stripe_event_id)
        if existing:
            return existing
        return self.events_repo.create_event(stripe_event_id, event_type, payload, procesado=False)

    def handle_event(self, event: dict[str, Any]) -> dict[str, Any]:
        event_id = event["id"]
        event_type = event["type"]
        stored = self.register_event(event_id, event_type, event)
        if stored.get("procesado"):
            return {"status": "already_processed", "event_id": event_id}

        try:
            handler = self._handlers().get(event_type)
            if handler:
                handler(event)
            self.events_repo.mark_processed(event_id)
            return {"status": "processed", "event_id": event_id}
        except Exception as exc:
            self.events_repo.mark_failed(event_id, str(exc))
            raise

    def _handlers(self) -> dict[str, Any]:
        return {
            "customer.subscription.created": self._handle_subscription_event,
            "customer.subscription.updated": self._handle_subscription_event,
            "customer.subscription.deleted": self._handle_subscription_event,
            "invoice.payment_succeeded": self._handle_invoice_event,
            "invoice.payment_failed": self._handle_invoice_event,
            "checkout.session.completed": self._handle_checkout_event,
        }

    def _handle_subscription_event(self, event: dict[str, Any]) -> None:
        obj = event.get("data", {}).get("object", {})
        stripe_subscription_id = obj.get("id")
        stripe_customer_id = obj.get("customer")
        if not stripe_subscription_id:
            return
        # Capture previous state for history
        existing = self.billing_repo.get_subscription_by_stripe_id(stripe_subscription_id) if hasattr(self.billing_repo, 'get_subscription_by_stripe_id') else None
        estado_anterior = existing.get("estado") if existing else None
        plan_anterior_id = existing.get("plan_id") if existing else None
        self.billing_repo.upsert_stripe_subscription_snapshot(
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            payload=obj,
        )
        # Write history if state changed
        try:
            updated = self.billing_repo.get_subscription_by_stripe_id(stripe_subscription_id)
            if updated and (updated.get("estado") != estado_anterior or updated.get("plan_id") != plan_anterior_id):
                self.billing_repo.create_suscripcion_historial(
                    suscripcion_id=updated.get("id"),
                    tipo_evento="SUBSCRIPTION_UPDATED",
                    estado_anterior=estado_anterior,
                    estado_nuevo=updated.get("estado"),
                    plan_anterior_id=plan_anterior_id,
                    plan_nuevo_id=updated.get("plan_id"),
                    descripcion=f"Evento Stripe: {event.get('type')}",
                )
        except Exception:
            pass

    def _handle_invoice_event(self, event: dict[str, Any]) -> None:
        obj = event.get("data", {}).get("object", {})
        result = self.billing_repo.upsert_stripe_invoice_snapshot(payload=obj)
        # If completed, create receipt
        try:
            if result and result.get("estado") == "COMPLETED" and result.get("id"):
                # Resolve institution via subscription customer (from invoice.metadata or subscription)
                sub_id = obj.get("subscription")
                if sub_id:
                    sub = self.billing_repo.get_subscription_by_stripe_id(sub_id)
                    if sub:
                        institu = None
                        try:
                            from app.repositories.institutions_repository import InstitutionsRepository
                            inst_repo = InstitutionsRepository()
                            # Try by customer via sub stripe_customer_id
                            customer_id = sub.get("stripe_customer_id")
                            if customer_id:
                                institu = inst_repo.get_by_customer_id(customer_id)
                        except Exception:
                            pass
                        if institu:
                            # Deduplicate by referencia_externa = invoice.number or id
                            invoice_number = obj.get("number") or obj.get("id")
                            existing = self.billing_repo.get_comprobante_by_referencia(str(invoice_number))
                            if not existing:
                                self.billing_repo.create_comprobante(
                                    institucion_id=institu.get("id"),
                                    pago_id=result["id"],
                                    tipo_comprobante="FACTURA",
                                    numero=str(invoice_number) if invoice_number else None,
                                    estado="COMPLETED",
                                    importe=result.get("importe") or (obj.get("amount_paid") or 0) / 100,
                                    moneda=(obj.get("currency") or "usd").upper(),
                                    referencia_externa=str(obj.get("id")),
                                    fecha_emision=obj.get("status_transitions", {}).get("paid_at"),
                                )
        except Exception:
            pass
        # On payment failed, mark subscription PENDING_PAYMENT
        try:
            if obj.get("status") == "open" and obj.get("collection_method") != "charge_automatically":
                pass  # not a failure
            if obj.get("status") == "uncollectible" or obj.get("billing_reason") == "subscription_cycle":
                # Check if failed explicitly (status transition)
                pass
            # Better: detect payment_failed event specifically (invoice.payment_failed)
            # In this handler event_type is invoice.payment_failed when called; update sub if subscription references exist
            sub_stripe_id = obj.get("subscription")
            if sub_stripe_id and (event.get("type") == "invoice.payment_failed" or obj.get("status") == "open" and obj.get("paid") is False):
                sub = self.billing_repo.get_subscription_by_stripe_id(sub_stripe_id)
                if sub and sub.get("estado") != "PENDING_PAYMENT":
                    self.billing_repo.update_subscription_stripe_refs(sub["id"], estado="PENDING_PAYMENT")
                    # History
                    self.billing_repo.create_suscripcion_historial(
                        suscripcion_id=sub["id"],
                        tipo_evento="PAYMENT_FAILED",
                        estado_anterior=sub.get("estado"),
                        estado_nuevo="PENDING_PAYMENT",
                        descripcion=f"Invoice {obj.get('id')} failed",
                    )
        except Exception:
            pass

    def _handle_checkout_event(self, event: dict[str, Any]) -> None:
        obj = event.get("data", {}).get("object", {})
        # Avoid duplicating pago if already processed by same checkout session
        session_id = obj.get("id")
        existing_pagos = self.billing_repo.client.table("pagos").select("*", count="exact").eq("stripe_checkout_session_id", session_id).execute()
        # If no existing checkout pago, insert PENDING
        if not (existing_pagos.data and len(existing_pagos.data) > 0):
            self.billing_repo.upsert_stripe_checkout_snapshot(payload=obj)
        # Activate subscription if linked
        sub_id = obj.get("subscription")
        if sub_id:
            sub = self.billing_repo.get_subscription_by_stripe_id(sub_id)
            if sub and sub.get("estado") != "ACTIVE":
                self.billing_repo.update_subscription_stripe_refs(
                    sub["id"],
                    estado="ACTIVE",
                    auto_renovacion=True,
                )
                # History
                try:
                    self.billing_repo.create_suscripcion_historial(
                        suscripcion_id=sub["id"],
                        tipo_evento="CHECKOUT_COMPLETED",
                        estado_anterior=sub.get("estado"),
                        estado_nuevo="ACTIVE",
                        descripcion=f"Checkout session completed: {session_id}",
                    )
                except Exception:
                    pass
