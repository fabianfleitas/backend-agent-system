from __future__ import annotations

"""Tests de notificaciones automáticas del webhook Stripe (PAYMENT_SUCCESS/FAILED,
SUBSCRIPTION_CANCELED/EXPIRED, PLAN_CHANGED) + idempotencia."""

from app.services.stripe_webhook_service import StripeWebhookService


class FakeEventsRepo:
    def __init__(self):
        self.events = {}

    def get_event(self, sid):
        return self.events.get(sid)

    def create_event(self, stripe_event_id, event_type, payload, procesado=False, error=None):
        self.events[stripe_event_id] = {"stripe_event_id": stripe_event_id, "procesado": procesado}
        return self.events[stripe_event_id]

    def mark_processed(self, sid):
        if sid in self.events:
            self.events[sid]["procesado"] = True

    def mark_failed(self, sid, error=None):
        if sid in self.events:
            self.events[sid]["procesado"] = False


class FakeBillingRepo:
    def __init__(self):
        self.subs = {"sub_1": {"id": 99, "estado": "TRIAL", "plan_id": 1, "institucion_id": 1, "stripe_customer_id": "cus_1"}}
        self.history = []
        self.failed_updates = []

    def get_subscription_by_stripe_id(self, sid):
        return self.subs.get(sid)

    def upsert_stripe_subscription_snapshot(self, stripe_subscription_id, stripe_customer_id, payload):
        status = payload.get("status")
        estado = "ACTIVE"
        if status == "canceled":
            estado = "CANCELLED"
        elif status == "incomplete_expired":
            estado = "EXPIRED"
        self.subs[stripe_subscription_id] = {
            "id": 99,
            "estado": estado,
            "plan_id": int((payload.get("metadata") or {}).get("plan_id") or 1),
            "institucion_id": 1,
            "stripe_customer_id": stripe_customer_id,
        }
        return self.subs[stripe_subscription_id]

    def create_suscripcion_historial(self, **kw):
        self.history.append(kw)
        return {"id": 1}

    def update_subscription_stripe_refs(self, sid, **kw):
        self.failed_updates.append((sid, kw))
        return {}

    def upsert_stripe_invoice_snapshot(self, payload):
        return {"id": 101, "estado": "COMPLETED", "importe": 10.0}

    def get_comprobante_by_referencia(self, ref):
        return None

    def create_comprobante(self, **kw):
        return {"id": 1}


class FakeInstitutionsRepo:
    def get_by_customer_id(self, cid):
        return {"id": 1}

    def get_institucion(self, institucion_id):
        return {"id": 1, "email_contacto": "billing@inst.edu"}


class FakeNotifications:
    def __init__(self):
        self.calls = []

    def send_automated(self, institucion_id, **kw):
        self.calls.append((institucion_id, kw.get("tipo"), kw.get("clave_idempotencia")))
        return {"id": 1, "estado": "SENT"}


def _svc(notifications=None):
    return StripeWebhookService(
        events_repo=FakeEventsRepo(),
        billing_repo=FakeBillingRepo(),
        notifications_service=notifications or FakeNotifications(),
        institutions_repo=FakeInstitutionsRepo(),
    )


def _sub_event(event_id, type, status, plan_id="1"):
    return {
        "id": event_id,
        "type": type,
        "data": {"object": {"id": "sub_1", "status": status, "customer": "cus_1", "metadata": {"plan_id": plan_id, "institucion_id": "1"}}},
    }


def test_payment_success_notifies():
    notif = FakeNotifications()
    svc = _svc(notif)
    svc.handle_event({
        "id": "evt_pay",
        "type": "invoice.payment_succeeded",
        "data": {"object": {"id": "in_1", "subscription": "sub_1", "status": "paid", "amount_paid": 1000, "currency": "usd", "customer": "cus_1", "status_transitions": {"paid_at": "2026-08-01T00:00:00Z"}, "number": "INV-001"}},
    })
    assert any(c[1] == "PAYMENT_SUCCESS" for c in notif.calls)


def test_payment_failed_notifies():
    notif = FakeNotifications()
    svc = _svc(notif)
    svc.handle_event({
        "id": "evt_fail",
        "type": "invoice.payment_failed",
        "data": {"object": {"id": "in_2", "subscription": "sub_1", "status": "open", "paid": False, "customer": "cus_1"}},
    })
    assert any(c[1] == "PAYMENT_FAILED" for c in notif.calls)


def test_subscription_canceled_notifies():
    notif = FakeNotifications()
    svc = _svc(notif)
    svc.handle_event(_sub_event("evt_cancel", "customer.subscription.deleted", "canceled"))
    assert any(c[1] == "SUBSCRIPTION_CANCELED" for c in notif.calls)


def test_subscription_expired_notifies():
    notif = FakeNotifications()
    svc = _svc(notif)
    svc.handle_event(_sub_event("evt_exp", "customer.subscription.updated", "incomplete_expired"))
    assert any(c[1] == "SUBSCRIPTION_EXPIRED" for c in notif.calls)


def test_plan_changed_notifies():
    notif = FakeNotifications()
    svc = _svc(notif)
    svc.handle_event(_sub_event("evt_plan", "customer.subscription.updated", "active", plan_id="2"))
    assert any(c[1] == "PLAN_CHANGED" for c in notif.calls)


def test_comprobante_dedupe_no_duplicate():
    class FakeBillingWithDedupe(FakeBillingRepo):
        def __init__(self):
            super().__init__()
            self.comprobantes_created = 0

        def get_comprobante_by_referencia(self, ref):
            return {"id": 999}  # ya existe → no crear

        def create_comprobante(self, **kw):
            self.comprobantes_created += 1
            return {"id": 1}

    billing = FakeBillingWithDedupe()
    svc = StripeWebhookService(
        events_repo=FakeEventsRepo(),
        billing_repo=billing,
        notifications_service=FakeNotifications(),
        institutions_repo=FakeInstitutionsRepo(),
    )
    svc.handle_event({
        "id": "evt_dedupe",
        "type": "invoice.payment_succeeded",
        "data": {"object": {"id": "in_1", "subscription": "sub_1", "status": "paid", "amount_paid": 1000, "currency": "usd", "customer": "cus_1", "status_transitions": {"paid_at": "2026-08-01T00:00:00Z"}, "number": "INV-001"}},
    })
    assert billing.comprobantes_created == 0


def test_webhook_idempotent_no_duplicate_notifications():
    notif = FakeNotifications()
    svc = _svc(notif)
    event = _sub_event("evt_dup", "customer.subscription.updated", "active", plan_id="2")
    first = svc.handle_event(event)
    second = svc.handle_event(event)
    assert first["status"] == "processed"
    assert second["status"] == "already_processed"
    assert notif.calls.count((1, "PLAN_CHANGED", "stripe-evt_dup-PLAN_CHANGED")) == 1