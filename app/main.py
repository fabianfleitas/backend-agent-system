from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, status

from app.api.router import router as api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.security import AuthContext, get_auth_context
from app.schemas.common import UserOut
from app.schemas.system import ReadyOut
from app.services.system_service import SystemService
from app.services.users_service import UsersService
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
        if not settings.supabase_configured:
            storage_ok = os.path.isdir(settings.storage_root)
            return ReadyOut(
                status="not_ready",
                services={
                    "database": False,
                    "openai": bool(settings.openai_api_key),
                    "vector_store": False,
                    "storage": storage_ok,
                },
            )
        return SystemService().get_readiness()

    @app.get("/me", response_model=UserOut)
    def me(auth: AuthContext = Depends(get_auth_context)) -> UserOut:
        try:
            return UsersService().get_or_create_current_user(auth)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Supabase user persistence is not available",
            ) from exc

    @app.on_event("startup")
    def _startup() -> None:
        ensure_dir(settings.storage_root)
        ensure_dir(settings.storage_audio_dir)
        ensure_dir(settings.storage_documents_dir)

    return app


app = create_app()
