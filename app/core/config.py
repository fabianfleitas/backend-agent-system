from __future__ import annotations

from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "backend-agent-system"
    environment: str = "local"
    api_prefix: str = "/api"

    storage_root: str = "storage"
    storage_audio_dir: str = "storage/audio"
    storage_documents_dir: str = "storage/documents"

    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY"),
    )
    supabase_storage_bucket_documents: str = "documents"
    supabase_storage_bucket_audio: str = "audio"

    openai_api_key: Optional[str] = None

    @property
    def supabase_project_url(self) -> Optional[str]:
        if not self.supabase_url:
            return None
        url = self.supabase_url.strip().rstrip("/")
        if url.endswith("/rest/v1"):
            url = url[: -len("/rest/v1")]
        return url

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_project_url and self.supabase_service_role_key)


settings = Settings()
