from __future__ import annotations

import os
from uuid import UUID

from fastapi import Depends, FastAPI

from app.api.router import router as api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.security import AuthContext, get_auth_context
from app.schemas.common import UserOut, UserRole
from app.schemas.system import ReadyOut
from app.services.mock_store import store
from app.utils.files import ensure_dir


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title=settings.app_name)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready", response_model=ReadyOut)
    def ready() -> ReadyOut:
        storage_ok = os.path.isdir(settings.storage_root)
        return ReadyOut(
            status="ready",
            services={
                "database": True,
                "openai": True,
                "vector_store": True,
                "storage": storage_ok,
            },
        )

    @app.get("/me", response_model=UserOut)
    def me(auth: AuthContext = Depends(get_auth_context)) -> UserOut:
        user = store.get_or_create_user(
            external_auth_id=auth.external_auth_id,
            auth_provider=auth.auth_provider,
            tipo_usuario=auth.tipo_usuario,
            correo=auth.correo,
        )
        role_map = {"ADMIN": UserRole.ADMIN, "SECRETARIA": UserRole.STAFF, "ESTUDIANTE": UserRole.STUDENT}
        return UserOut(
            external_auth_id=user.external_auth_id,
            email=user.correo,
            role=role_map.get(user.tipo_usuario, UserRole.STUDENT),
            created_at=user.fecha_creacion,
            updated_at=user.fecha_creacion,
        )

    @app.on_event("startup")
    def _startup() -> None:
        ensure_dir(settings.storage_root)
        ensure_dir(settings.storage_audio_dir)
        ensure_dir(settings.storage_documents_dir)

    return app


app = create_app()
