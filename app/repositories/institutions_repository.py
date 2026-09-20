from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class InstitutionsRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def get_institucion(self, institucion_id: int) -> Optional[dict]:
        resp = self.client.table("instituciones").select("*").eq("id", institucion_id).limit(1).execute()
        return resp.data[0] if resp.data else None

    def update_stripe_customer_id(self, institucion_id: int, stripe_customer_id: str) -> Optional[dict]:
        resp = (
            self.client.table("instituciones")
            .update({"stripe_customer_id": stripe_customer_id})
            .eq("id", institucion_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def create_institucion(
        self,
        nombre: str,
        codigo: Optional[str] = None,
        nombre_comercial: Optional[str] = None,
        ciudad: Optional[str] = None,
        pais: Optional[str] = None,
        direccion: Optional[str] = None,
        email_contacto: Optional[str] = None,
        telefono_contacto: Optional[str] = None,
    ) -> dict:
        payload: dict = {
            "nombre": nombre,
            "activo": True,
        }
        if codigo is not None:
            payload["codigo"] = codigo
        if nombre_comercial is not None:
            payload["nombre_comercial"] = nombre_comercial
        if ciudad is not None:
            payload["ciudad"] = ciudad
        if pais is not None:
            payload["pais"] = pais
        if direccion is not None:
            payload["direccion"] = direccion
        if email_contacto is not None:
            payload["email_contacto"] = email_contacto
        if telefono_contacto is not None:
            payload["telefono_contacto"] = telefono_contacto
        resp = self.client.table("instituciones").insert(payload).execute()
        return resp.data[0]

    def update_institucion(self, institucion_id: int, **campos) -> Optional[dict]:
        payload = {k: v for k, v in campos.items() if v is not None}
        if not payload:
            return self.get_institucion(institucion_id)
        resp = (
            self.client.table("instituciones")
            .update(payload)
            .eq("id", institucion_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def deactivate_institucion(self, institucion_id: int) -> Optional[dict]:
        resp = (
            self.client.table("instituciones")
            .update({"activo": False})
            .eq("id", institucion_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def get_by_customer_id(self, stripe_customer_id: str) -> Optional[dict]:
        resp = self.client.table("instituciones").select("*").eq("stripe_customer_id", stripe_customer_id).limit(1).execute()
        return resp.data[0] if resp.data else None

    def list_instituciones(self, activo: bool = True) -> list[dict]:
        q = self.client.table("instituciones").select("*").eq("activo", activo).order("nombre")
        resp = q.execute()
        return list(resp.data or [])

    def get_active_membership(self, external_auth_id: str) -> Optional[dict]:
        # una sola membresía activa por usuario (membresía única)
        # Intentar determinista: si hay >1 (por datos históricos), usar la más reciente y loggear
        resp = (
            self.client.table("institucion_miembros")
            .select("*, instituciones(nombre) as nombre_institucion")
            .eq("external_auth_id", external_auth_id)
            .eq("activo", True)
            .is_("fecha_salida", None)
            .order("fecha_ingreso", desc=True)
            .execute()
        )
        rows = resp.data or []
        if len(rows) > 1:
            import logging
            logging.getLogger(__name__).warning(
                "Duplicate active memberships for %s: %d found; using most recent (id=%s, inst=%s)",
                external_auth_id, len(rows), rows[0].get("id"), rows[0].get("institucion_id"),
            )
        if rows:
            row = rows[0]
            return {
                "institucion_id": row.get("institucion_id"),
                "tipo_miembro": row.get("tipo_miembro"),
                "nombre_institucion": row.get("nombre_institucion") or row.get("instituciones", {}).get("nombre"),
            }
        return None

    def is_platform_admin(self, external_auth_id: str) -> bool:
        resp = (
            self.client.table("platform_admins")
            .select("*")
            .eq("external_auth_id", external_auth_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return bool(resp.data and resp.data[0])

    def list_members(self, institucion_id: int) -> list[dict]:
        resp = (
            self.client.table("institucion_miembros")
            .select("*, app_users(email, full_name)")
            .eq("institucion_id", institucion_id)
            .eq("activo", True)
            .execute()
        )
        return list(resp.data or [])

    def add_member(self, institucion_id: int, external_auth_id: str, tipo_miembro: str) -> dict:
        # Regla: un usuario no debe pertenecer a varias instituciones simultáneamente
        existing = self.client.table("institucion_miembros").select("*").eq("external_auth_id", external_auth_id).eq("activo", True).execute()
        for row in (existing.data or []):
            if row.get("institucion_id") != institucion_id:
                raise ValueError("User already has active membership in another institution")
            # Si ya es miembro activo de esta misma institución, no duplicar
            if row.get("institucion_id") == institucion_id:
                return row
        try:
            resp = (
                self.client.table("institucion_miembros")
                .insert({
                    "institucion_id": institucion_id,
                    "external_auth_id": external_auth_id,
                    "tipo_miembro": tipo_miembro,
                    "activo": True,
                })
                .execute()
            )
            return resp.data[0]
        except Exception as exc:
            # Capturar violación de unicidad DB como defensa adicional
            msg = str(exc).lower()
            if "unique" in msg or "constraint" in msg or "duplicate" in msg or "institution" in msg:
                # Intentar leer si ya existía (race)
                existing_after = self.client.table("institucion_miembros").select("*").eq("external_auth_id", external_auth_id).eq("activo", True).execute()
                for row in (existing_after.data or []):
                    if row.get("institucion_id") == institucion_id:
                        return row
                raise ValueError("User already has active membership in another institution") from exc
            raise

    def deactivate_member(self, membre_id: int) -> dict:
        resp = (
            self.client.table("institucion_miembros")
            .update({"activo": False, "fecha_salida": "now()"})
            .eq("id", membre_id)
            .execute()
        )
        return resp.data[0] if resp.data else {}
