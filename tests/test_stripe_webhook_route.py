from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.billing import routes as billing_routes


class _FakeStripeService:
    configured = True

    def verify_webhook_event(self, *, payload: bytes, signature_header: str):
        return type(
            "VerifiedEvent",
            (),
            {
                "event_id": "evt_123",
                "event_type": "customer.subscription.created",
                "payload": json.loads(payload.decode("utf-8")),
            },
        )()


class _FakeWebhookService:
    def handle_event(self, event):
        return {"status": "processed", "event_id": event["id"]}


def test_stripe_webhook_route_accepts_verified_event(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(billing_routes.router, prefix="/api/billing")

    monkeypatch.setattr(billing_routes, "get_stripe_agent_service", lambda: _FakeStripeService())
    monkeypatch.setattr(billing_routes, "StripeWebhookService", lambda: _FakeWebhookService())

    client = TestClient(app)
    resp = client.post(
        "/api/billing/stripe/webhook",
        headers={"Stripe-Signature": "sig"},
        content=json.dumps({"id": "evt_123", "type": "customer.subscription.created"}).encode("utf-8"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["event_id"] == "evt_123"
