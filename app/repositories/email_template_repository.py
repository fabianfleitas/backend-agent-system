from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class EmailTemplateRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def get_template(self, codigo: str, institucion_id: Optional[int]) -> Optional[dict]:
        # Precedencia institucional > global
        if institucion_id is not None:
            resp = (
                self.client.table("plantillas_email")
                .select("*")
                .eq("codigo", codigo)
                .eq("institucion_id", institucion_id)
                .eq("activo", True)
                .limit(1)
                .execute()
            )
            if resp.data:
                return resp.data[0]
        resp = (
            self.client.table("plantillas_email")
            .select("*")
            .eq("codigo", codigo)
            .is_("institucion_id", None)
            .eq("activo", True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def list_by_institution(self, institucion_id: int) -> list[dict]:
        resp = (
            self.client.table("plantillas_email")
            .select("*")
            .eq("institucion_id", institucion_id)
            .order("nombre")
            .execute()
        )
        return list(resp.data or [])

    def list_global(self) -> list[dict]:
        resp = (
            self.client.table("plantillas_email")
            .select("*")
            .is_("institucion_id", None)
            .order("nombre")
            .execute()
        )
        return list(resp.data or [])

    def create(
        self,
        *,
        institucion_id: Optional[int],
        codigo: str,
        nombre: str,
        asunto: str,
        contenido_html: str,
        contenido_texto: Optional[str] = None,
        activo: bool = True,
    ) -> dict:
        payload: dict = {
            "institucion_id": institucion_id,
            "codigo": codigo,
            "nombre": nombre,
            "asunto": asunto,
            "contenido_html": contenido_html,
            "contenido_texto": contenido_texto,
            "activo": activo,
        }
        resp = self.client.table("plantillas_email").insert(payload).execute()
        return resp.data[0]

    def update(self, template_id: int, **campos) -> Optional[dict]:
        payload = {k: v for k, v in campos.items() if v is not None}
        if not payload:
            resp = self.client.table("plantillas_email").select("*").eq("id", template_id).limit(1).execute()
            return resp.data[0] if resp.data else None
        resp = (
            self.client.table("plantillas_email")
            .update(payload)
            .eq("id", template_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def deactivate(self, template_id: int) -> Optional[dict]:
        resp = (
            self.client.table("plantillas_email")
            .update({"activo": False})
            .eq("id", template_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def get_by_id(self, template_id: int) -> Optional[dict]:
        resp = (
            self.client.table("plantillas_email")
            .select("*")
            .eq("id", template_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None