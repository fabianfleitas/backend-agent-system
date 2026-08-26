from __future__ import annotations

from typing import Optional

from app.core.security import AuthContext
from app.repositories.categories_repository import CategoriesRepository


class CategoriesService:
    def __init__(self, repository: Optional[CategoriesRepository] = None) -> None:
        self.repository = repository or CategoriesRepository()

    def list_by_institution(self, auth: AuthContext) -> list[dict]:
        if auth.institucion_id is None and not auth.is_platform_admin:
            return []
        institution_id = None if auth.is_platform_admin else auth.institucion_id
        if institution_id is None:
            return []
        return self.repository.list_by_institution(institution_id)

    def get_by_id(self, categoria_id: int, auth: AuthContext) -> Optional[dict]:
        if auth.institucion_id is None and not auth.is_platform_admin:
            return None
        institution_id = None if auth.is_platform_admin else auth.institucion_id
        if institution_id is None:
            return None
        return self.repository.get_by_id(categoria_id, institution_id)
