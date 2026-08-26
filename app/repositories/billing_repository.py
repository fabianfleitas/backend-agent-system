from __future__ import annotations

from typing import Optional, Any

from app.core.supabase import get_supabase_client


class BillingRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def list_planes(self, activo: bool = True) -> list[dict]:
        q = self.client.table("planes").select("*").eq("activo", activo).order("nombre")
        resp = q.execute()
        return list(resp.data or [])

    def get_plan(self, plan_id: int) -> Optional[dict]:
        resp = self.client.table("planes").select("*").eq("id", plan_id).limit(1).execute()
        return resp.data[0] if resp.data else None

    def get_subscription_by_institution(self, institucion_id: int) -> Optional[dict]:
        # Suscripción más reciente por institución
        resp = (
            self.client.table("suscripciones")
            .select("*, planes!inner(id, nombre, precio, moneda, intervalo, features, activo)")
            .eq("institucion_id", institucion_id)
            .order("fecha_inicio", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def list_subscriptions(self, institucion_id: Optional[int] = None) -> list[dict]:
        q = self.client.table("suscripciones").select("*, planes!inner(id, nombre, precio, moneda, intervalo, features, activo)")
        if institucion_id is not None:
            q = q.eq("institucion_id", institucion_id)
        resp = q.execute()
        return list(resp.data or [])

    def list_pagos(self, institucion_id: Optional[int] = None) -> list[dict]:
        q = self.client.table("pagos").select("*").order("fecha_pago", desc=True)
        if institucion_id is not None:
            q = q.eq("institucion_id", institucion_id)
        resp = q.execute()
        return list(resp.data or [])

    def list_comprobantes(self, institucion_id: Optional[int] = None) -> list[dict]:
        q = self.client.table("comprobantes").select("*").order("fecha_emision", desc=True)
        if institucion_id is not None:
            q = q.eq("institucion_id", institucion_id)
        resp = q.execute()
        return list(resp.data or [])
