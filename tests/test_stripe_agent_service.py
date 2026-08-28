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
