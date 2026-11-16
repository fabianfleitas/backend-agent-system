from __future__ import annotations

import logging
from typing import Optional

from app.core.security import AuthContext
from app.repositories.billing_repository import BillingRepository
from app.repositories.institutions_repository import InstitutionsRepository
from app.services.stripe_agent_service import get_stripe_agent_service

logger = logging.getLogger(__name__)


def _log_billing_action(action: str, auth: AuthContext, detalle: Optional[str] = None) -> None:
    try:
        from app.repositories.audit_repository import AuditRepository

        AuditRepository().log_action(
            action,
            external_auth_id=auth.external_auth_id,
            institucion_id=auth.institucion_id,
            detalle=detalle,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audit action %s failed: %s", action, exc)


class BillingService:
    def __init__(
        self,
        repo: Optional[BillingRepository] = None,
        institutions_repo: Optional[InstitutionsRepository] = None,
    ) -> None:
        self.repo = repo or BillingRepository()
        self.institutions_repo = institutions_repo or InstitutionsRepository()

    def _institution_id(self, auth: Optional[AuthContext]) -> Optional[int]:
        if auth is not None and not auth.is_platform_admin:
            return auth.institucion_id
        return None

    def get_subscription(self, auth: Optional[AuthContext] = None) -> Optional[dict]:
        inst = self._institution_id(auth)
        if inst is None:
            return None
        return self.repo.get_subscription_by_institution(inst)

    def get_active_subscription(self, auth: Optional[AuthContext] = None) -> Optional[dict]:
        inst = self._institution_id(auth)
        if inst is None:
            return None
        return self.repo.get_active_subscription_by_institution(inst)

    def get_plan_for_subscription(self, auth: Optional[AuthContext] = None) -> Optional[dict]:
        sub = self.get_subscription(auth)
        if sub and sub.get("plan_id"):
            return self.repo.get_plan(sub["plan_id"])
        return None

    def list_subscriptions(self, auth: Optional[AuthContext] = None) -> list[dict]:
        inst = self._institution_id(auth)
        return self.repo.list_subscriptions(inst)

    def list_pagos(self, auth: Optional[AuthContext] = None) -> list[dict]:
        inst = self._institution_id(auth)
        return self.repo.list_pagos(inst)

    def list_comprobantes(self, auth: Optional[AuthContext] = None) -> list[dict]:
        inst = self._institution_id(auth)
        return self.repo.list_comprobantes(inst)

    def get_subscription_history(self, auth: Optional[AuthContext] = None, suscripcion_id: Optional[int] = None) -> list[dict]:
        sub = self.get_subscription(auth)
        sid = suscripcion_id or (sub.get("id") if sub else None)
        if sid is None:
            return []
        return self.repo.list_suscripcion_historial(sid)

    def list_plans(self) -> list[dict]:
        return self.repo.list_planes()

    def list_plans_for_admin(self) -> list[dict]:
        plans = self.repo.list_planes()
        return [p for p in plans if p.get("stripe_price_id")]

    def create_subscription_for_institution(self, auth: AuthContext, plan_id: int) -> dict:
        if auth.is_platform_admin:
            raise PermissionError("Platform admin cannot create institutional subscriptions directly")
        if not auth.institucion_id:
            raise PermissionError("Institution membership required")

        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise ValueError("Plan not found")
        if not plan.get("stripe_price_id"):
            raise ValueError("Plan is not synced with Stripe")

        institution = self.institutions_repo.get_institucion(auth.institucion_id)
        if not institution:
            raise ValueError("Institution not found")

        stripe_service = get_stripe_agent_service()
        if not stripe_service.configured:
            raise RuntimeError("Stripe is not configured")

        stripe_customer_id = institution.get("stripe_customer_id")
        if not stripe_customer_id:
            customer = stripe_service.create_customer(
                email=auth.email or f"institution-{auth.institucion_id}@example.local",
                name=institution.get("nombre"),
                metadata={"institucion_id": str(auth.institucion_id)},
            )
            stripe_customer_id = customer["id"]
            self.institutions_repo.update_stripe_customer_id(auth.institucion_id, stripe_customer_id)

        subscription = stripe_service.create_subscription(
            customer_id=stripe_customer_id,
            price_id=plan["stripe_price_id"],
            metadata={
                "institucion_id": str(auth.institucion_id),
                "plan_id": str(plan["id"]),
            },
        )
        self.repo.upsert_stripe_subscription_snapshot(
            stripe_subscription_id=subscription["id"],
            stripe_customer_id=stripe_customer_id,
            payload=subscription,
        )
        _log_billing_action(
            "BILLING_CREATE_SUBSCRIPTION",
            auth,
            f"plan_id={plan['id']} stripe_subscription_id={subscription['id']}",
        )
        return subscription

    def cancel_subscription_for_institution(self, auth: AuthContext, cancel_at_period_end: bool = True) -> dict:
        if auth.is_platform_admin:
            raise PermissionError("Platform admin cannot cancel institutional subscriptions directly")
        if not auth.institucion_id:
            raise PermissionError("Institution membership required")

        subscription = self.get_subscription(auth)
        if not subscription or not subscription.get("stripe_subscription_id"):
            raise ValueError("Subscription not found")

        stripe_service = get_stripe_agent_service()
        if not stripe_service.configured:
            raise RuntimeError("Stripe is not configured")

        updated = stripe_service.cancel_subscription(
            subscription["stripe_subscription_id"],
            cancel_at_period_end=cancel_at_period_end,
        )
        estado = self._map_subscription_state(updated.get("status"))
        fecha_cancelacion = updated.get("canceled_at")
        self.repo.update_subscription_stripe_refs(
            subscription["id"],
            estado=estado,
            cancelacion_programada=bool(updated.get("cancel_at_period_end", False)),
            fecha_cancelacion=str(fecha_cancelacion) if fecha_cancelacion else None,
        )
        _log_billing_action("BILLING_CANCEL", auth, f"subscription_id={subscription['id']}")
        return updated

    def reactivate_subscription_for_institution(self, auth: AuthContext) -> dict:
        if auth.is_platform_admin:
            raise PermissionError("Platform admin cannot reactivate institutional subscriptions directly")
        if not auth.institucion_id:
            raise PermissionError("Institution membership required")

        subscription = self.get_subscription(auth)
        if not subscription or not subscription.get("stripe_subscription_id"):
            raise ValueError("Subscription not found")

        stripe_service = get_stripe_agent_service()
        if not stripe_service.configured:
            raise RuntimeError("Stripe is not configured")

        updated = stripe_service.reactivate_subscription(subscription["stripe_subscription_id"])
        estado = self._map_subscription_state(updated.get("status"))
        self.repo.update_subscription_stripe_refs(
            subscription["id"],
            estado=estado,
            cancelacion_programada=bool(updated.get("cancel_at_period_end", False)),
            fecha_cancelacion=None,
        )
        _log_billing_action("BILLING_REACTIVATE", auth, f"subscription_id={subscription['id']}")
        return updated

    def create_checkout_session_for_institution(self, auth: AuthContext, plan_id: int, success_url: str, cancel_url: str) -> dict:
        if auth.is_platform_admin:
            raise PermissionError("Platform admin cannot create institutional checkout")
        if not auth.institucion_id:
            raise PermissionError("Institution membership required")
        plan = self.repo.get_plan(plan_id)
        if not plan or not plan.get("stripe_price_id"):
            raise ValueError("Plan not synced with Stripe")
        institution = self.institutions_repo.get_institucion(auth.institucion_id)
        stripe_service = get_stripe_agent_service()
        if not stripe_service.configured:
            raise RuntimeError("Stripe not configured")
        stripe_customer_id = institution.get("stripe_customer_id") if institution else None
        if not stripe_customer_id:
            customer = stripe_service.create_customer(
                email=auth.email or f"institution-{auth.institucion_id}@example.local",
                name=institution.get("nombre") if institution else None,
                metadata={"institucion_id": str(auth.institucion_id)},
            )
            stripe_customer_id = customer["id"]
            self.institutions_repo.update_stripe_customer_id(auth.institucion_id, stripe_customer_id)
        session = stripe_service.create_checkout_session(
            customer_id=stripe_customer_id,
            price_id=plan["stripe_price_id"],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"institucion_id": str(auth.institucion_id), "plan_id": str(plan["id"])},
            subscription_data={
                "metadata": {
                    "institucion_id": str(auth.institucion_id),
                    "plan_id": str(plan["id"]),
                }
            },
        )
        # stripe-python v15: Session es objeto; usar .to_dict() para dict seguro
        session_dict = session.to_dict() if hasattr(session, "to_dict") else dict(session)
        _log_billing_action(
            "BILLING_CHECKOUT",
            auth,
            f"plan_id={plan['id']} session_id={session_dict.get('id')}",
        )
        return session_dict

    def get_stripe_subscription(self, auth: AuthContext) -> dict:
        if auth.is_platform_admin:
            raise PermissionError("Platform admin cannot query institutional Stripe subscription directly")
        subscription = self.get_subscription(auth)
        if not subscription or not subscription.get("stripe_subscription_id"):
            raise ValueError("Subscription not found")
        stripe_service = get_stripe_agent_service()
        if not stripe_service.configured:
            raise RuntimeError("Stripe is not configured")
        return stripe_service.retrieve_subscription(subscription["stripe_subscription_id"])

    def create_billing_portal_session(self, auth: AuthContext, return_url: str) -> dict:
        if auth.is_platform_admin:
            raise PermissionError("Platform admin cannot create portal sessions directly")
        subscription = self.get_subscription(auth)
        if not subscription:
            raise ValueError("Subscription not found")
        stripe_customer_id = subscription.get("stripe_customer_id")
        if not stripe_customer_id:
            institution = self.institutions_repo.get_institucion(auth.institucion_id)
            stripe_customer_id = institution.get("stripe_customer_id") if institution else None
        if not stripe_customer_id:
            raise ValueError("Stripe customer not found")
        stripe_service = get_stripe_agent_service()
        if not stripe_service.configured:
            raise RuntimeError("Stripe is not configured")
        _log_billing_action("BILLING_PORTAL", auth, f"institucion_id={auth.institucion_id}")
        return stripe_service.create_billing_portal_session(customer_id=stripe_customer_id, return_url=return_url)

    def change_subscription_plan(self, auth: AuthContext, plan_id: int) -> dict:
        if auth.is_platform_admin:
            raise PermissionError("Platform admin cannot change institutional subscriptions directly")
        if not auth.institucion_id:
            raise PermissionError("Institution membership required")
        subscription = self.get_subscription(auth)
        if not subscription or not subscription.get("stripe_subscription_id"):
            raise ValueError("Subscription not found")
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise ValueError("Plan not found")
        if not plan.get("stripe_price_id"):
            raise ValueError("Plan is not synced with Stripe")
        stripe_service = get_stripe_agent_service()
        if not stripe_service.configured:
            raise RuntimeError("Stripe is not configured")
        updated = stripe_service.update_subscription_price(subscription["stripe_subscription_id"], plan["stripe_price_id"])
        # Update local plan reference if price changed
        self.repo.update_subscription_stripe_refs(
            subscription["id"],
            plan_id=plan["id"],
            estado=self._map_subscription_state(updated.get("status")),
            cancelacion_programada=bool(updated.get("cancel_at_period_end", False)),
        )
        _log_billing_action("BILLING_CHANGE_PLAN", auth, f"subscription_id={subscription['id']} plan_id={plan['id']}")
        return updated

    def _map_subscription_state(self, stripe_status: Optional[str]) -> str:
        mapping = {
            "trialing": "TRIAL",
            "active": "ACTIVE",
            "past_due": "PENDING_PAYMENT",
            "unpaid": "SUSPENDED",
            "canceled": "CANCELLED",
            "incomplete_expired": "EXPIRED",
            "incomplete": "PENDING_PAYMENT",
        }
        return mapping.get((stripe_status or "").lower(), "PENDING_PAYMENT")
