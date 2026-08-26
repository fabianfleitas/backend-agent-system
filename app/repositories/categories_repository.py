from __future__ import annotations

from typing import Any, Optional

from app.core.supabase import get_supabase_client


class CategoriesRepository:
    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or get_supabase_client()

    def list_by_institution(self, institucion_id: int) -> list[dict]:
        response = (
            self.client.table("categorias")
            .select("*")
            .eq("institucion_id", institucion_id)
            .eq("activo", True)
            .execute()
        )
        return list(response.data or [])

    def get_by_id(self, categoria_id: int, institucion_id: int) -> Optional[dict]:
        response = (
            self.client.table("categorias")
            .select("*")
            .eq("id", categoria_id)
            .eq("institucion_id", institucion_id)
            .eq("activo", True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None
