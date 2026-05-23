from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "backend-agent-system"
    environment: str = "local"
    api_prefix: str = "/api"

    storage_root: str = "storage"
    storage_audio_dir: str = "storage/audio"
    storage_documents_dir: str = "storage/documents"


settings = Settings()
