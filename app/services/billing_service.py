from __future__ import annotations

from typing import Optional

from app.core.security import AuthContext
from app.repositories.billing_repository import BillingRepository


class BillingService:
    def __init__(self, repo: Optional[BillingRepository] = None) -> None:
        self.repo = repo or BillingRepository()

    def _institution_id(self, auth: Optional[AuthContext]) -> Optional[int]:
        if auth is not None and not auth.is_platform_admin:
            return auth.institucion_id
        return None

    def get_subscription(self, auth: Optional[AuthContext] = None) -> Optional[dict]:
        inst = self._institution_id(auth)
        if inst is None:
            return None
        return self.repo.get_subscription_by_institution(inst)

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

    def list_plans(self) -> list[dict]:
        return self.repo.list_planes()
