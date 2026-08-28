from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

from app.core.config import settings


@dataclass(frozen=True)
class StripeRuntimeConfig:
    secret_key: str
    webhook_secret: Optional[str] = None
    api_version: str = "2024-06-20"
    account_id: Optional[str] = None


def get_stripe_runtime_config() -> Optional[StripeRuntimeConfig]:
    if not settings.stripe_secret_key:
        return None
    return StripeRuntimeConfig(
        secret_key=settings.stripe_secret_key,
        webhook_secret=settings.stripe_webhook_secret,
        api_version=settings.stripe_api_version,
        account_id=settings.stripe_account_id,
    )


@lru_cache
def get_stripe_client() -> Any:
    runtime = get_stripe_runtime_config()
    if runtime is None:
        raise RuntimeError("Stripe is not configured. Set STRIPE_SECRET_KEY.")

    try:
        import stripe
    except ImportError as exc:
        raise RuntimeError("The 'stripe' package is not installed. Run `pip install -r requirements.txt`.") from exc

    stripe.api_key = runtime.secret_key
    stripe.api_version = runtime.api_version
    if runtime.account_id:
        stripe.account = runtime.account_id
    return stripe


def is_stripe_configured() -> bool:
    return get_stripe_runtime_config() is not None
