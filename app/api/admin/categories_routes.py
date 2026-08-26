from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import AuthContext, get_admin_auth
from app.schemas.admin import CategoryOut
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.services.categories_service import CategoriesService

router = APIRouter()


def _get_service() -> CategoriesService:
    return CategoriesService()


@router.get("/categories", response_model=PaginatedResponse[CategoryOut])
def list_categories(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_admin_auth),
) -> PaginatedResponse[CategoryOut]:
    items = _get_service().list_by_institution(auth)
    total = len(items)
    page = items[offset : offset + limit]
    return PaginatedResponse[CategoryOut](
        items=[CategoryOut(**i) for i in page],
        pagination=PaginationMeta(total=total, limit=limit, offset=offset),
    )
