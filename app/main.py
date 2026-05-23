from __future__ import annotations

from fastapi import FastAPI

from app.api.router import router as api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.utils.files import ensure_dir


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title=settings.app_name)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.on_event("startup")
    def _startup() -> None:
        ensure_dir(settings.storage_root)
        ensure_dir(settings.storage_audio_dir)
        ensure_dir(settings.storage_documents_dir)

    return app


app = create_app()
