from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import AuthContext, get_admin_auth
from app.schemas.admin import CategoryIn, CategoryOut
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.services.categories_service import CategoriesService

router = APIRouter()


def _get_service() -> CategoriesService:
    return CategoriesService()


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryIn,
    auth: AuthContext = Depends(get_admin_auth),
) -> CategoryOut:
    result = _get_service().create(auth, payload.nombre, payload.descripcion)
    return CategoryOut(**result)

@router.put("/categories/{categoria_id}", response_model=CategoryOut)
def update_category(
    categoria_id: int,
    payload: CategoryIn,
    auth: AuthContext = Depends(get_admin_auth),
) -> CategoryOut:
    result = _get_service().update(auth, categoria_id, payload.nombre, payload.descripcion)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return CategoryOut(**result)

@router.delete("/categories/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_category(
    categoria_id: int,
    auth: AuthContext = Depends(get_admin_auth),
) -> None:
    result = _get_service().deactivate(auth, categoria_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

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
