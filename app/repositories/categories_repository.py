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

    def list_global(self) -> list[dict]:
        response = (
            self.client.table("categorias")
            .select("*")
            .is_("institucion_id", "null")
            .eq("activo", True)
            .execute()
        )
        return list(response.data or [])

    def list_by_institution_and_global(self, institucion_id: int) -> list[dict]:
        """Categorías institucionales + globales con precedencia institucional.

        Si existe una categoría institucional con el mismo nombre (case-insensitive)
        que una global, gana la institucional (se descarta la global).
        """
        by_key: dict[str, dict] = {}
        for c in self.list_global():
            by_key[str(c.get("nombre", "")).strip().lower()] = c
        for c in self.list_by_institution(institucion_id):
            by_key[str(c.get("nombre", "")).strip().lower()] = c
        return list(by_key.values())

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

    def get_by_id_with_global(self, categoria_id: int, institucion_id: int) -> Optional[dict]:
        """Resuelve primero la categoría institucional y, si no existe, la global."""
        result = self.get_by_id(categoria_id, institucion_id)
        if result is not None:
            return result
        response = (
            self.client.table("categorias")
            .select("*")
            .eq("id", categoria_id)
            .is_("institucion_id", "null")
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
