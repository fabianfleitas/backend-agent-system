from __future__ import annotations

from app.services.stripe_webhook_service import StripeWebhookService
from app.repositories.billing_repository import BillingRepository
from unittest.mock import MagicMock

class FakeRepo:
    def __init__(self):
        self.events = {}
    def get_event(self, sid): return self.events.get(sid)
    def create_event(self, **kw):
        self.events[kw.get("stripe_event_id")] = {"procesado": False, **kw}
        return self.events[kw.get("stripe_event_id")]
    def mark_processed(self, sid):
        if sid in self.events: self.events[sid]["procesado"] = True
    def get_subscription_by_stripe_id(self, sid):
        return {"id": 99, "estado": "TRIAL", "stripe_subscription_id": sid, "plan_id": 1}
    def upsert_stripe_subscription_snapshot(self, **kw):
        return {"id": 99, "estado": "ACTIVE", "plan_id": 1}
    def update_subscription_stripe_refs(self, sid, **kw): pass
    def create_suscripcion_historial(self, **kw): return {"id": 1}
    def create_comprobante(self, **kw): return {"id": 1}
    def get_comprobante_by_referencia(self, ref): return None
    def upsert_stripe_invoice_snapshot(self, payload):
        return {"id": 101, "estado": "COMPLETED", "importe": 10.0, "stripe_payment_intent_id": "pi_1"}
    def get_subscription_by_stripe_id(self, sid): return {"id": 99, "estado": "TRIAL"}
    def client(self):
        return MagicMock()

class FakeEventsRepo:
    def __init__(self):
        self.events = {}
    def get_event(self, sid): return self.events.get(sid)
    def create_event(self, stripe_event_id, event_type, payload, procesado=False, error=None):
        self.events[stripe_event_id] = {"stripe_event_id": stripe_event_id, "procesado": procesado}
        return self.events[stripe_event_id]
    def mark_processed(self, sid):
        if sid in self.events: self.events[sid]["procesado"] = True
    def mark_failed(self, sid, error=None):
        if sid in self.events: self.events[sid]["procesado"] = False

def test_webhook_subscription_update_history():
    svc = StripeWebhookService(events_repo=FakeEventsRepo(), billing_repo=FakeRepo())
    result = svc.handle_event({"id":"evt_1","type":"customer.subscription.updated","data":{"object":{"id":"sub_1","status":"active","cancel_at_period_end":False,"current_period_start":"2026-01-01","current_period_end":"2026-02-01","items":[{"price":"price_1"}],"metadata":{"plan_id":"1","institucion_id":"1"}}}})
    assert result["status"] == "processed"

def test_webhook_invoice_payment_succeeded_comprobante():
    svc = StripeWebhookService(events_repo=FakeEventsRepo(), billing_repo=FakeRepo())
    result = svc.handle_event({"id":"evt_2","type":"invoice.payment_succeeded","data":{"object":{"id":"in_1","subscription":"sub_1","status":"paid","amount_paid":1000,"currency":"usd","customer":"cus_1","status_transitions":{"paid_at":"2026-08-01T00:00:00Z"},"number":"INV-001"}}})
    assert result["status"] == "processed"
