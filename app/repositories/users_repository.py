from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.security import AuthContext


class UsersRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def get_memberships_batch(self, external_auth_ids: list[str]) -> dict[str, dict]:
        # Fetch active membership + platform admin for batch
        result: dict[str, dict] = {}
        if not external_auth_ids:
            return result
        # Institution membership (singleton per user expected; take first active)
        resp = (
            self.client.table("institucion_miembros")
            .select("external_auth_id, institucion_id, tipo_miembro, activo")
            .in_("external_auth_id", external_auth_ids)
            .eq("activo", True)
            .execute()
        )
        for row in (resp.data or []):
            eid = row.get("external_auth_id")
            if eid and eid not in result:
                result[eid] = {
                    "institucion_id": row.get("institucion_id"),
                    "tipo_miembro": row.get("tipo_miembro"),
                }
        # Platform admins (soft-delete: columna real es is_active)
        resp_plat = (
            self.client.table("platform_admins")
            .select("external_auth_id, is_active")
            .in_("external_auth_id", external_auth_ids)
            .eq("is_active", True)
            .execute()
        )
        for row in (resp_plat.data or []):
            eid = row.get("external_auth_id")
            if eid:
                result.setdefault(eid, {})
                result[eid]["is_platform_admin"] = True
        return result

    def get_user_by_external_auth_id(self, external_auth_id: str) -> Optional[dict]:
        response = (
            self.client.table("app_users")
            .select("*")
            .eq("external_auth_id", external_auth_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def create_user(
        self,
        external_auth_id: str,
        email: str,
        role: str,
        full_name: Optional[str] = None,
    ) -> dict:
        response = (
            self.client.table("app_users")
            .insert(
                {
                    "external_auth_id": external_auth_id,
                    "email": email,
                    "role": role,
                    "full_name": full_name,
                }
            )
            .execute()
        )
        return response.data[0]

    def get_or_create_user(self, auth_context: AuthContext) -> dict:
        existing = self.get_user_by_external_auth_id(auth_context.external_auth_id)
        if existing:
            return existing

        # role deprecado; se determina por membresía institucional
        role = "STUDENT"
        email = auth_context.email or _fallback_email(auth_context.external_auth_id)
        try:
            return self.create_user(
                external_auth_id=auth_context.external_auth_id,
                email=email,
                role=role,
                full_name=auth_context.full_name,
            )
        except Exception:
            existing_after_race = self.get_user_by_external_auth_id(auth_context.external_auth_id)
            if existing_after_race:
                return existing_after_race
            raise

    def update_user(self, external_auth_id: str, full_name: Optional[str] = None) -> Optional[dict]:
        payload: dict = {}
        if full_name is not None:
            payload["full_name"] = full_name
        if not payload:
            return self.get_user_by_external_auth_id(external_auth_id)
        response = (
            self.client.table("app_users")
            .update(payload)
            .eq("external_auth_id", external_auth_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def remove_user(self, external_auth_id: str) -> bool:
        """Eliminación lógica (soft delete) del usuario: desactiva app_users,
        membresía institucional activa y rol de platform admin (cascada)."""
        user_updated = (
            self.client.table("app_users")
            .update({"is_active": False})
            .eq("external_auth_id", external_auth_id)
            .execute()
        )
        if not user_updated.data:
            return False
        # Cascada: desactivar membresía activa en instituciones
        try:
            self.client.table("institucion_miembros").update({"activo": False, "fecha_salida": "now()"}).eq(
                "external_auth_id", external_auth_id
            ).eq("activo", True).execute()
        except Exception:
            pass
        # Cascada: revocar platform admin (soft)
        try:
            self.client.table("platform_admins").update({"is_active": False}).eq(
                "external_auth_id", external_auth_id
            ).execute()
        except Exception:
            pass
        return True

    def list_platform_admins(self) -> list[dict]:
        response = (
            self.client.table("platform_admins")
            .select("*, app_users(email, full_name)")
            .order("created_at", desc=True)
            .execute()
        )
        return list(response.data or [])

    def grant_platform_admin(self, external_auth_id: str) -> dict:
        response = (
            self.client.table("platform_admins")
            .upsert(
                {"external_auth_id": external_auth_id, "is_active": True},
                on_conflict="external_auth_id",
            )
            .execute()
        )
        return response.data[0] if response.data else {}

    def revoke_platform_admin(self, external_auth_id: str) -> bool:
        response = (
            self.client.table("platform_admins")
            .update({"is_active": False})
            .eq("external_auth_id", external_auth_id)
            .execute()
        )
        return bool(response.data)

    def list_users(self, institucion_id: Optional[int] = None) -> list[dict]:
        query = self.client.table("app_users").select("*")
        if institucion_id is not None:
            # Filtrar solo miembros activos de esta institución
            membro_resp = (
                self.client.table("institucion_miembros")
                .select("external_auth_id")
                .eq("institucion_id", institucion_id)
                .eq("activo", True)
                .execute()
            )
            members = [m["external_auth_id"] for m in (membro_resp.data or [])]
            if members:
                query = query.in_("external_auth_id", members)
            else:
                return []  # Ningún miembro
        response = query.order("created_at", desc=True).execute()
        return list(response.data or [])


def _fallback_email(external_auth_id: str) -> str:
    safe_id = external_auth_id.replace("@", "_at_").replace(" ", "_")
    return f"{safe_id}@delegated.local"
