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

    def get_subscription_by_stripe_id(self, stripe_subscription_id: str) -> Optional[dict]:
        resp = self.client.table("suscripciones").select("*").eq("stripe_subscription_id", stripe_subscription_id).limit(1).execute()
        return resp.data[0] if resp.data else None

    def get_comprobante_by_referencia(self, referencia_externa: str) -> Optional[dict]:
        resp = self.client.table("comprobantes").select("*").eq("referencia_externa", referencia_externa).limit(1).execute()
        return resp.data[0] if resp.data else None

    def get_plan_by_price_id(self, stripe_price_id: str) -> Optional[dict]:
        resp = self.client.table("planes").select("*").eq("stripe_price_id", stripe_price_id).limit(1).execute()
        return resp.data[0] if resp.data else None

    def get_plan(self, plan_id: int) -> Optional[dict]:
        resp = self.client.table("planes").select("*").eq("id", plan_id).limit(1).execute()
        return resp.data[0] if resp.data else None

    def create_plan(
        self,
        nombre: str,
        codigo: Optional[str] = None,
        descripcion: Optional[str] = None,
        precio: Optional[float] = None,
        moneda: Optional[str] = None,
        intervalo: Optional[str] = None,
        max_documentos: Optional[int] = None,
        max_usuarios: Optional[int] = None,
        max_estudiantes: Optional[int] = None,
        features: Optional[dict] = None,
    ) -> dict:
        payload: dict = {"nombre": nombre, "activo": True}
        if codigo is not None:
            payload["codigo"] = codigo
        if descripcion is not None:
            payload["descripcion"] = descripcion
        if precio is not None:
            payload["precio"] = precio
        if moneda is not None:
            payload["moneda"] = moneda
        if intervalo is not None:
            payload["intervalo"] = intervalo
        if max_documentos is not None:
            payload["max_documentos"] = max_documentos
        if max_usuarios is not None:
            payload["max_usuarios"] = max_usuarios
        if max_estudiantes is not None:
            payload["max_estudiantes"] = max_estudiantes
        if features is not None:
            payload["features"] = features
        resp = self.client.table("planes").insert(payload).execute()
        return resp.data[0]

    def update_plan(self, plan_id: int, **campos) -> Optional[dict]:
        payload = {k: v for k, v in campos.items() if v is not None}
        if not payload:
            return self.get_plan(plan_id)
        resp = (
            self.client.table("planes")
            .update(payload)
            .eq("id", plan_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def deactivate_plan(self, plan_id: int) -> Optional[dict]:
        resp = (
            self.client.table("planes")
            .update({"activo": False})
            .eq("id", plan_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def update_plan_stripe_refs(self, plan_id: int, *, stripe_product_id: Optional[str] = None, stripe_price_id: Optional[str] = None) -> Optional[dict]:
        payload = {}
        if stripe_product_id is not None:
            payload["stripe_product_id"] = stripe_product_id
        if stripe_price_id is not None:
            payload["stripe_price_id"] = stripe_price_id
        if not payload:
            return self.get_plan(plan_id)
        resp = self.client.table("planes").update(payload).eq("id", plan_id).execute()
        return resp.data[0] if resp.data else None

    def update_subscription_stripe_refs(
        self,
        suscripcion_id: int,
        *,
        stripe_subscription_id: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        estado: Optional[str] = None,
        cancelacion_programada: Optional[bool] = None,
        fecha_cancelacion: Optional[str] = None,
        plan_id: Optional[int] = None,
    ) -> Optional[dict]:
        payload = {}
        if stripe_subscription_id is not None:
            payload["stripe_subscription_id"] = stripe_subscription_id
        if stripe_customer_id is not None:
            payload["stripe_customer_id"] = stripe_customer_id
        if estado is not None:
            payload["estado"] = estado
        if cancelacion_programada is not None:
            payload["cancelacion_programada"] = cancelacion_programada
        if fecha_cancelacion is not None:
            payload["fecha_cancelacion"] = fecha_cancelacion
        if plan_id is not None:
            payload["plan_id"] = plan_id
        if not payload:
            return self.get_subscription_by_id(suscripcion_id)
        resp = self.client.table("suscripciones").update(payload).eq("id", suscripcion_id).execute()
        return resp.data[0] if resp.data else None

    def get_subscription_by_id(self, suscripcion_id: int) -> Optional[dict]:
        resp = self.client.table("suscripciones").select("*").eq("id", suscripcion_id).limit(1).execute()
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

    def get_active_subscription_by_institution(self, institucion_id: int) -> Optional[dict]:
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

    def list_suscripcion_historial(self, suscripcion_id: int) -> list[dict]:
        resp = (
            self.client.table("suscripcion_historial")
            .select("*")
            .eq("suscripcion_id", suscripcion_id)
            .order("created_at", desc=True)
            .execute()
        )
        return list(resp.data or [])

    def create_suscripcion_historial(
        self,
        suscripcion_id: int,
        tipo_evento: str,
        estado_anterior: Optional[str] = None,
        estado_nuevo: Optional[str] = None,
        plan_anterior_id: Optional[int] = None,
        plan_nuevo_id: Optional[int] = None,
        descripcion: Optional[str] = None,
        external_auth_id: Optional[str] = None,
    ) -> dict:
        resp = self.client.table("suscripcion_historial").insert({
            "suscripcion_id": suscripcion_id,
            "tipo_evento": tipo_evento,
            "estado_anterior": estado_anterior,
            "estado_nuevo": estado_nuevo,
            "plan_anterior_id": plan_anterior_id,
            "plan_nuevo_id": plan_nuevo_id,
            "descripcion": descripcion,
            "external_auth_id": external_auth_id,
        }).execute()
        return resp.data[0] if resp.data else {}

    def create_comprobante(
        self,
        institucion_id: int,
        pago_id: int,
        tipo_comprobante: str = "FACTURA",
        numero: Optional[str] = None,
        estado: str = "COMPLETED",
        importe: Optional[float] = None,
        moneda: str = "USD",
        archivo_path: Optional[str] = None,
        proveedor: Optional[str] = "stripe",
        referencia_externa: Optional[str] = None,
        fecha_emision: Optional[str] = None,
    ) -> dict:
        resp = self.client.table("comprobantes").insert({
            "institucion_id": institucion_id,
            "pago_id": pago_id,
            "tipo_comprobante": tipo_comprobante,
            "numero": numero,
            "estado": estado,
            "importe": importe,
            "moneda": moneda,
            "archivo_path": archivo_path,
            "proveedor": proveedor,
            "referencia_externa": referencia_externa,
            "fecha_emision": fecha_emision,
        }).execute()
        return resp.data[0] if resp.data else {}

    def list_comprobantes(self, institucion_id: Optional[int] = None) -> list[dict]:
        q = self.client.table("comprobantes").select("*").order("fecha_emision", desc=True)
        if institucion_id is not None:
            q = q.eq("institucion_id", institucion_id)
        resp = q.execute()
        return list(resp.data or [])

    def upsert_stripe_subscription_snapshot(self, *, stripe_subscription_id: str, stripe_customer_id: Optional[str], payload: dict) -> dict:
        existing = (
            self.client.table("suscripciones")
            .select("*")
            .eq("stripe_subscription_id", stripe_subscription_id)
            .limit(1)
            .execute()
        )
        update_payload = {
            "stripe_customer_id": stripe_customer_id,
            "estado": self._map_subscription_state(payload.get("status")),
            "auto_renovacion": not bool(payload.get("cancel_at_period_end", False)),
        }
        # Sync plan_id via price
        def _get_items(data):
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return []
        items_raw = payload.get("items")
        items = _get_items(items_raw)
        stripe_price_id = items[0].get("price") if items else None
        if not stripe_price_id and payload.get("plan") is None:
            # Try from metadata if available in payload
            stripe_price_id = (payload.get("metadata") or {}).get("stripe_price_id")
        if stripe_price_id:
            plan = self.get_plan_by_price_id(stripe_price_id)
            if plan:
                update_payload["plan_id"] = plan["id"]
        # Sync dates
        def _ts_to_iso(val):
            if val is None:
                return None
            if isinstance(val, (int, float)):
                from datetime import datetime, timezone
                return datetime.fromtimestamp(val, tz=timezone.utc).isoformat()
            return val
        current_period_start = _ts_to_iso(payload.get("current_period_start"))
        current_period_end = _ts_to_iso(payload.get("current_period_end"))
        if current_period_start:
            update_payload["fecha_inicio"] = current_period_start
        if current_period_end:
            update_payload["fecha_vencimiento"] = current_period_end
        if existing.data:
            resp = (
                self.client.table("suscripciones")
                .update(update_payload)
                .eq("stripe_subscription_id", stripe_subscription_id)
                .execute()
            )
            return resp.data[0]
        # Resolve plan from price for insert
        items_raw = payload.get("items")
        items = _get_items(items_raw)
        stripe_price_id = items[0].get("price") if items else None
        if not stripe_price_id:
            stripe_price_id = (payload.get("metadata") or {}).get("stripe_price_id")
        plan_id_for_insert = payload.get("metadata", {}).get("plan_id")
        if stripe_price_id and not plan_id_for_insert:
            plan = self.get_plan_by_price_id(stripe_price_id)
            if plan:
                plan_id_for_insert = plan["id"]
        insert_payload = {
            "institucion_id": payload.get("metadata", {}).get("institucion_id"),
            "plan_id": plan_id_for_insert or payload.get("metadata", {}).get("plan_id"),
            "estado": self._map_subscription_state(payload.get("status")),
            "stripe_subscription_id": stripe_subscription_id,
            "stripe_customer_id": stripe_customer_id,
            "auto_renovacion": not bool(payload.get("cancel_at_period_end", False)),
        }
        current_period_start = _ts_to_iso(payload.get("current_period_start"))
        current_period_end = _ts_to_iso(payload.get("current_period_end"))
        if current_period_start:
            insert_payload["fecha_inicio"] = current_period_start
        if current_period_end:
            insert_payload["fecha_vencimiento"] = current_period_end
        resp = self.client.table("suscripciones").insert(insert_payload).execute()
        return resp.data[0]

    def upsert_stripe_invoice_snapshot(self, *, payload: dict) -> dict:
        stripe_payment_intent_id = payload.get("payment_intent")
        stripe_customer_id = payload.get("customer")
        checkout_session_id = payload.get("checkout_session")
        existing = None
        if stripe_payment_intent_id:
            existing = (
                self.client.table("pagos")
                .select("*")
                .eq("stripe_payment_intent_id", stripe_payment_intent_id)
                .limit(1)
                .execute()
            )
        if existing and existing.data:
            resp = (
                self.client.table("pagos")
                .update({
                    "estado": self._map_receipt_state(payload.get("status")),
                    "stripe_charge_id": payload.get("charge"),
                })
                .eq("stripe_payment_intent_id", stripe_payment_intent_id)
                .execute()
            )
            return resp.data[0]
        resp = self.client.table("pagos").insert({
            "institucion_id": payload.get("metadata", {}).get("institucion_id"),
            "suscripcion_id": payload.get("metadata", {}).get("suscripcion_id"),
            "importe": (payload.get("amount_paid") or 0) / 100,
            "moneda": (payload.get("currency") or "usd").upper(),
            "estado": self._map_receipt_state(payload.get("status")),
            "proveedor": "stripe",
            "stripe_payment_intent_id": stripe_payment_intent_id,
            "stripe_checkout_session_id": checkout_session_id,
            "stripe_charge_id": payload.get("charge"),
            "descripcion": payload.get("description"),
            "fecha_pago": payload.get("status_transitions", {}).get("paid_at"),
        }).execute()
        return resp.data[0]

    def upsert_stripe_checkout_snapshot(self, *, payload: dict) -> dict:
        resp = self.client.table("pagos").insert({
            "institucion_id": payload.get("metadata", {}).get("institucion_id"),
            "suscripcion_id": payload.get("metadata", {}).get("suscripcion_id"),
            "importe": (payload.get("amount_total") or 0) / 100,
            "moneda": (payload.get("currency") or "usd").upper(),
            "estado": "PENDING",
            "proveedor": "stripe",
            "stripe_checkout_session_id": payload.get("id"),
            "descripcion": payload.get("mode"),
        }).execute()
        return resp.data[0]

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

    def _map_receipt_state(self, stripe_status: Optional[str]) -> str:
        mapping = {
            "paid": "COMPLETED",
            "open": "PENDING",
            "void": "FAILED",
            "uncollectible": "FAILED",
            "draft": "PENDING",
        }
        return mapping.get((stripe_status or "").lower(), "PENDING")
