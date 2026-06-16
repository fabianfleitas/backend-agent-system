from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import settings


@lru_cache
def get_supabase_client() -> Any:
    if not settings.supabase_configured:
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )

    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "The 'supabase' package is not installed. Run `pip install -r requirements.txt`."
        ) from exc

    return create_client(settings.supabase_project_url, settings.supabase_service_role_key)
