from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from app.core.security import AuthContext
from app.repositories.categories_repository import CategoriesRepository


class CategoriesService:
    def __init__(self, repository: Optional[CategoriesRepository] = None) -> None:
        self.repository = repository or CategoriesRepository()

    def create(self, auth: AuthContext, nombre: str, descripcion: Optional[str] = None) -> dict:
        if auth.institucion_id is None and not auth.is_platform_admin:
            raise HTTPException(status_code=403, detail="Institution membership required")
        return self.repository.create(auth.institucion_id, nombre, descripcion)

    def update(self, auth: AuthContext, categoria_id: int, nombre: Optional[str] = None, descripcion: Optional[str] = None) -> Optional[dict]:
        if auth.institucion_id is None and not auth.is_platform_admin:
            raise HTTPException(status_code=403, detail="Institution membership required")
        return self.repository.update(categoria_id, auth.institucion_id, nombre=nombre, descripcion=descripcion)

    def deactivate(self, auth: AuthContext, categoria_id: int) -> Optional[dict]:
        if auth.institucion_id is None and not auth.is_platform_admin:
            raise HTTPException(status_code=403, detail="Institution membership required")
        return self.repository.deactivate(categoria_id, auth.institucion_id)

    def get_by_id(self, auth: AuthContext, categoria_id: int) -> Optional[dict]:
        if auth.institucion_id is None and not auth.is_platform_admin:
            return None
        institution_id = auth.institucion_id if not auth.is_platform_admin else None
        if institution_id is not None:
            return self.repository.get_by_id(categoria_id, institution_id)
        # Platform admin: direct lookup by id (repo filter activo=True applies)
        return self.repository.get_by_id_any(categoria_id)

    def list_by_institution(self, auth: AuthContext) -> list[dict]:
        if auth.institucion_id is None and not auth.is_platform_admin:
            return []
        institution_id = None if auth.is_platform_admin else auth.institucion_id
        if institution_id is None:
            return []
        return self.repository.list_by_institution(institution_id)
