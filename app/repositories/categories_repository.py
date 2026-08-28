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

    def get_by_id_any(self, categoria_id: int) -> Optional[dict]:
        response = (
            self.client.table("categorias")
            .select("*")
            .eq("id", categoria_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def create(self, institucion_id: int, nombre: str, descripcion: Optional[str]) -> dict:
        resp = (
            self.client.table("categorias")
            .insert({
                "institucion_id": institucion_id,
                "nombre": nombre,
                "descripcion": descripcion,
                "activo": True,
            })
            .execute()
        )
        return resp.data[0] if resp.data else {}

    def update(self, categoria_id: int, institucion_id: int, nombre: Optional[str] = None, descripcion: Optional[str] = None, activo: Optional[bool] = None) -> Optional[dict]:
        updates = {}
        if nombre is not None:
            updates["nombre"] = nombre
        if descripcion is not None:
            updates["descripcion"] = descripcion
        if activo is not None:
            updates["activo"] = activo
        if not updates:
            return None
        resp = (
            self.client.table("categorias")
            .update(updates)
            .eq("id", categoria_id)
            .eq("institucion_id", institucion_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def deactivate(self, categoria_id: int, institucion_id: int) -> Optional[dict]:
        return self.update(categoria_id, institucion_id, activo=False)
