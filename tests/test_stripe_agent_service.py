from __future__ import annotations

from unittest.mock import patch

from app.core.config import settings
from app.services.stripe_agent_service import StripeAgentService


def test_stripe_agent_service_reports_unconfigured_when_secret_missing() -> None:
    with patch.object(settings, "stripe_secret_key", None):
        # Re-evaluate configured property after monkeypatching settings directly
        service = StripeAgentService()
        assert service.configured is False


def test_stripe_agent_service_reports_configured_when_secret_present() -> None:
    service = StripeAgentService()
    assert service.configured is True


class _FakeResource:
    """Emula un recurso de stripe-python v15 (objeto con .to_dict(), no dict)."""

    def __init__(self, data: dict) -> None:
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class _FakeStripe:
    class Subscription:
        @staticmethod
        def retrieve(sid, expand=None):
            return _FakeResource({"id": sid, "status": "active", "items": {"data": [{"id": "si_1"}]}})

        @staticmethod
        def modify(sid, **kwargs):
            return _FakeResource({"id": sid, "status": "active", "cancel_at_period_end": kwargs.get("cancel_at_period_end", False)})

        @staticmethod
        def cancel(sid):
            return _FakeResource({"id": sid, "status": "canceled"})

    class Customer:
        @staticmethod
        def create(**kwargs):
            return _FakeResource({"id": "cus_1", "email": kwargs.get("email")})


def _service_with_fake_stripe(monkeypatch) -> StripeAgentService:
    service = StripeAgentService()
    monkeypatch.setattr("app.services.stripe_agent_service.get_stripe_client", lambda: _FakeStripe())
    return service


def test_retrieve_subscription_returns_plain_dict(monkeypatch) -> None:
    service = _service_with_fake_stripe(monkeypatch)
    result = service.retrieve_subscription("sub_1")
    assert isinstance(result, dict)
    assert result.get("id") == "sub_1"
    assert result.get("status") == "active"


def test_cancel_subscription_returns_plain_dict(monkeypatch) -> None:
    service = _service_with_fake_stripe(monkeypatch)
    result = service.cancel_subscription("sub_1")
    assert isinstance(result, dict)
    assert result.get("cancel_at_period_end") is True


def test_update_subscription_price_returns_plain_dict(monkeypatch) -> None:
    service = _service_with_fake_stripe(monkeypatch)
    result = service.update_subscription_price("sub_1", "price_1")
    assert isinstance(result, dict)
    assert result.get("id") == "sub_1"


def test_create_customer_returns_plain_dict(monkeypatch) -> None:
    service = _service_with_fake_stripe(monkeypatch)
    result = service.create_customer(email="a@b.com")
    assert isinstance(result, dict)
    assert result.get("id") == "cus_1"
