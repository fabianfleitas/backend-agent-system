from __future__ import annotations

from typing import Any, Optional

from app.core.security import AuthContext
from app.core.supabase import get_supabase_client


class UsersRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

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

        role = _map_role(auth_context.tipo_usuario)
        email = auth_context.correo or _fallback_email(auth_context.external_auth_id)
        try:
            return self.create_user(
                external_auth_id=auth_context.external_auth_id,
                email=email,
                role=role,
            )
        except Exception:
            existing_after_race = self.get_user_by_external_auth_id(auth_context.external_auth_id)
            if existing_after_race:
                return existing_after_race
            raise

    def list_users(self) -> list[dict]:
        response = (
            self.client.table("app_users")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return list(response.data or [])


def _map_role(tipo_usuario: str) -> str:
    mapping = {"ADMIN": "ADMIN", "SECRETARIA": "STAFF", "ESTUDIANTE": "STUDENT"}
    return mapping.get(tipo_usuario, "STUDENT")


def _fallback_email(external_auth_id: str) -> str:
    safe_id = external_auth_id.replace("@", "_at_").replace(" ", "_")
    return f"{safe_id}@delegated.local"
