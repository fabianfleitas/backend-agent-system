from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.core.config import settings
from app.integrations.stripe_client import get_stripe_client, get_stripe_runtime_config, is_stripe_configured


@dataclass(frozen=True)
class StripeWebhookVerification:
    event_id: str
    event_type: str
    livemode: bool
    payload: dict[str, Any]


class StripeAgentService:
    def __init__(self) -> None:
        self._client = None

    @property
    def configured(self) -> bool:
        return is_stripe_configured()

    @property
    def runtime_config(self):
        return get_stripe_runtime_config()

    def client(self):
        if self._client is None:
            self._client = get_stripe_client()
        return self._client

    def create_customer(self, *, email: str, name: Optional[str] = None, metadata: Optional[dict[str, str]] = None) -> dict[str, Any]:
        stripe = self.client()
        payload: dict[str, Any] = {"email": email}
        if name:
            payload["name"] = name
        if metadata:
            payload["metadata"] = metadata
        return stripe.Customer.create(**payload)

    def create_subscription(self, *, customer_id: str, price_id: str, metadata: Optional[dict[str, str]] = None) -> dict[str, Any]:
        stripe = self.client()
        payload: dict[str, Any] = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "payment_behavior": "default_incomplete",
            "expand": ["latest_invoice.payment_intent"],
        }
        if metadata:
            payload["metadata"] = metadata
        sub = stripe.Subscription.create(**payload)
        return sub.to_dict() if hasattr(sub, "to_dict") else dict(sub)

    def cancel_subscription(self, subscription_id: str, *, cancel_at_period_end: bool = True) -> dict[str, Any]:
        stripe = self.client()
        if cancel_at_period_end:
            return stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        return stripe.Subscription.cancel(subscription_id)

    def reactivate_subscription(self, subscription_id: str) -> dict[str, Any]:
        stripe = self.client()
        return stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)

    def update_subscription_price(self, subscription_id: str, price_id: str) -> dict[str, Any]:
        stripe = self.client()
        current = stripe.Subscription.retrieve(subscription_id)
        item_id = None
        items = (current.get("items") or {}).get("data") or []
        if items:
            item_id = items[0].get("id")
        payload: dict[str, Any] = {
            "items": [{"id": item_id, "price": price_id}] if item_id else [{"price": price_id}],
            "proration_behavior": "create_prorations",
            "expand": ["latest_invoice.payment_intent"],
        }
        return stripe.Subscription.modify(subscription_id, **payload)

    def create_billing_portal_session(self, *, customer_id: str, return_url: str) -> dict[str, Any]:
        stripe = self.client()
        return stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

    def create_or_update_product(self, *, name: str, description: Optional[str] = None, metadata: Optional[dict[str, str]] = None, stripe_product_id: Optional[str] = None) -> dict[str, Any]:
        stripe = self.client()
        payload: dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        if metadata:
            payload["metadata"] = metadata
        if stripe_product_id:
            return stripe.Product.modify(stripe_product_id, **payload)
        return stripe.Product.create(**payload)

    def create_or_update_price(
        self,
        *,
        product_id: str,
        unit_amount: int,
        currency: str = "usd",
        recurring_interval: Optional[str] = "month",
        metadata: Optional[dict[str, str]] = None,
        stripe_price_id: Optional[str] = None,
        active: bool = True,
    ) -> dict[str, Any]:
        stripe = self.client()
        payload: dict[str, Any] = {
            "product": product_id,
            "unit_amount": unit_amount,
            "currency": currency.lower(),
            "active": active,
        }
        if recurring_interval:
            payload["recurring"] = {"interval": recurring_interval}
        if metadata:
            payload["metadata"] = metadata
        if stripe_price_id:
            return stripe.Price.modify(stripe_price_id, active=active, metadata=metadata or {})
        return stripe.Price.create(**payload)

    def create_checkout_session(
        self,
        *,
        customer_id: Optional[str] = None,
        price_id: str,
        success_url: str,
        cancel_url: str,
        mode: str = "subscription",
        metadata: Optional[dict[str, str]] = None,
        subscription_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        stripe = self.client()
        payload: dict[str, Any] = {
            "line_items": [{"price": price_id, "quantity": 1}],
            "mode": mode,
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if customer_id:
            payload["customer"] = customer_id
        if metadata:
            payload["metadata"] = metadata
        if subscription_data:
            payload["subscription_data"] = subscription_data
        return stripe.checkout.Session.create(**payload)

    def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        stripe = self.client()
        return stripe.Subscription.retrieve(subscription_id, expand=["latest_invoice.payment_intent"])

    def verify_webhook_event(self, *, payload: bytes, signature_header: str) -> StripeWebhookVerification:
        runtime = self.runtime_config
        if runtime is None or not runtime.webhook_secret:
            raise RuntimeError("Stripe webhook secret is not configured. Set STRIPE_WEBHOOK_SECRET.")
        stripe = self.client()
        event = stripe.Webhook.construct_event(payload, signature_header, runtime.webhook_secret)
        event_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        return StripeWebhookVerification(
            event_id=event_dict.get("id"),
            event_type=event_dict.get("type"),
            livemode=bool(event_dict.get("livemode", False)),
            payload=event_dict,
        )


def get_stripe_agent_service() -> StripeAgentService:
    return StripeAgentService()
