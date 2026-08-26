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
        # Platform admins
        resp_plat = (
            self.client.table("platform_admins")
            .select("external_auth_id, is_platform_admin")
            .in_("external_auth_id", external_auth_ids)
            .eq("is_platform_admin", True)
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
