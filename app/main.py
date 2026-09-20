from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router as api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.security import AuthContext, get_auth_context
from app.schemas.common import UserOut, UserUpdateIn
from app.schemas.system import ReadyOut
from app.services.system_service import SystemService
from app.services.users_service import UsersService
from app.utils.files import ensure_dir
from app.core.rate_limit import RateLimiter, RateLimitMiddleware, RateLimitRule


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        openapi_url="/openapi.json",
        docs_url="/docs",
    )

    def _custom_openapi() -> dict:
        from fastapi.openapi.utils import get_openapi
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=settings.app_name + " — Backend Multiinstitución",
            version="1.0.0",
            description=(
                "API institucional con RAG, voz, historial, auditoría y billing de lectura. "
                "Aislamiento por institución. Auth: JWT Supabase. "
                "Errores comunes: 401 (JWT faltante/inválido), 403 (permiso institucional), 404 (recurso no encontrado o cross-tenant), "
                "409 (conflicto / membresía duplicada), 422 (validación de entrada), 500 (error interno). "
                "Paginación: limit/offset; filtros por institución, documento, modelo, categoría, período."
            ),
            routes=app.routes,
            # Security scheme for Supabase JWT Bearer
            openapi_version="3.1.0",
        )
        openapi_schema["info"]["contact"] = {"name": "Soporte institucional", "url": "https://example.org"}
        openapi_schema["servers"] = [{"url": "/api", "description": "API local"}]
        openapi_schema["tags"] = [
            {"name": "global", "description": "Health, ready, me"},
            {"name": "chat", "description": "Texto, voz, feedback"},
            {"name": "conversations", "description": "Historial e interacciones"},
            {"name": "admin", "description": "Administración institucional (docs, audit, metrics, config, billing)"},
            {"name": "categories", "description": "Categorías institucionales"},
            {"name": "platform", "description": "Administración global / platform admin (instituciones, usuarios globales, metrics, audit, billing)"},
        ]
        # Security scheme (Supabase JWT Bearer)
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        openapi_schema["components"]["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT (Supabase Auth)",
            }
        }
        openapi_schema["security"] = [{"bearerAuth": []}]
        app.openapi_schema = openapi_schema
        return openapi_schema

    app.openapi = _custom_openapi

    def _split(value: str) -> list[str]:
        return [v.strip() for v in value.split(",") if v.strip()]

    allow_origins = ["*"] if settings.cors_allow_origins == "*" else _split(settings.cors_allow_origins)
    allow_methods = ["*"] if settings.cors_allow_methods == "*" else _split(settings.cors_allow_methods)
    allow_headers = ["*"] if settings.cors_allow_headers == "*" else _split(settings.cors_allow_headers)
    if allow_origins == ["*"]:
        allow_credentials = False
    else:
        allow_credentials = settings.cors_allow_credentials

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
        allow_credentials=allow_credentials,
    )

    # Rate limiting middleware (in-memory token bucket; per-process)
    limiter = RateLimiter()
    rules = []
    for part in (settings.rate_limit_rules or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            prefix, limit, window = part.split(":")
            rules.append(RateLimitRule(prefix=prefix, limit=int(limit), window_seconds=int(window)))
        except Exception:
            pass
    app.add_middleware(
        RateLimitMiddleware,
        limiter=limiter,
        rules=rules,
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.exception_handler(Exception)
    async def _internal_error_handler(request, exc: Exception):
        # No exponer detalles internos; los 500 devuelven un JSON limpio.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

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

    @app.put("/me", response_model=UserOut)
    def update_me(
        payload: UserUpdateIn,
        auth: AuthContext = Depends(get_auth_context),
    ) -> UserOut:
        try:
            return UsersService().update_current_user(auth, full_name=payload.full_name)
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
