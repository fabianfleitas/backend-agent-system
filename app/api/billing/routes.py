from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.services.stripe_agent_service import get_stripe_agent_service
from app.services.stripe_webhook_service import StripeWebhookService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
) -> dict:
    if not stripe_signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe-Signature header")

    payload = await request.body()
    service = get_stripe_agent_service()
    if not service.configured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe is not configured")

    try:
        verified = service.verify_webhook_event(payload=payload, signature_header=stripe_signature)
    except Exception as exc:
        logger.warning("Stripe webhook verification failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe webhook signature") from exc

    result = StripeWebhookService().handle_event(verified.payload)
    return {
        "ok": True,
        "event_id": verified.event_id,
        "event_type": verified.event_type,
        "result": result,
    }
