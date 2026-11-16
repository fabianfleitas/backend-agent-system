from __future__ import annotations

from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "backend-agent-system"
    environment: str = "local"
    api_prefix: str = "/api"

    cors_allow_origins: str = "*"
    cors_allow_methods: str = "*"
    cors_allow_headers: str = "*"
    cors_allow_credentials: bool = False

    storage_root: str = "storage"
    storage_audio_dir: str = "storage/audio"
    storage_documents_dir: str = "storage/documents"

    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY"),
    )
    supabase_jwt_secret: Optional[str] = Field(
        default=None, alias="SUPABASE_JWT_SECRET"
    )
    supabase_storage_bucket_documents: str = "documents"
    supabase_storage_bucket_audio: str = "audio"

    openai_api_key: Optional[str] = None

    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    stripe_api_version: str = "2024-06-20"
    stripe_account_id: Optional[str] = None

    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-oss-20b"
    llm_enabled: bool = False
    llm_temperature: float = 0.2
    llm_max_tokens: int = 384
    llm_request_timeout: float = 45.0
    llm_max_retries: int = 1
    # Enrutamiento opcional de OpenRouter para generación (coma-separado).
    # Ej.: "Groq" o "Groq,DeepInfra". Vacío = enrutamiento automático.
    llm_provider_order: str = ""
    llm_provider_allow_fallbacks: bool = True
    # Nivel de razonamiento para modelos que lo soportan: low|medium|high.
    llm_reasoning_effort: str = ""

    llm_history_enabled: bool = True
    llm_history_max_tokens: int = 1500
    llm_history_max_messages: int = 10

    judge_enabled: bool = False
    judge_model: str = "openai/gpt-4o-mini"
    judge_temperature: float = 0.0
    judge_max_tokens: int = 256
    judge_request_timeout: float = 45.0
    # Fracción de consultas interactivas que se evalúan con el juez cuando
    # judge_enabled=true. 0.0 = ninguna (protege el SLO de latencia RNF-05);
    # 1.0 = todas (usar en corridas de evaluación, no en interactivo).
    judge_sample_rate: float = 0.0

    handoff_enabled: bool = False
    handoff_trigger_on_guard: bool = True
    handoff_trigger_on_llm_failure: bool = True
    handoff_frustration_enabled: bool = False
    handoff_frustration_keywords: str = (
        "no me sirve,no entiendo,inútil,mala atención,quej,hablar con alguien,"
        "persona real,operador,secretaría,reclamo"
    )

    stt_enabled: bool = False
    stt_model: str = "x-ai/grok-stt-1.0"
    stt_response_format: str = "verbose_json"
    stt_request_timeout: float = 60.0
    stt_max_retries: int = 1

    tts_enabled: bool = False
    tts_model: str = "hexgrad/kokoro-82m"
    tts_voice: str = "ef_dora"
    tts_response_format: str = "mp3"
    tts_max_input_chars: int = 4000
    tts_request_timeout: float = 60.0
    tts_max_retries: int = 1

    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embeddings_enabled: bool = False
    embedding_batch_size: int = 64
    embedding_max_tokens_per_chunk: int = 8191
    embedding_request_timeout: float = 30.0
    embedding_max_retries: int = 2

    indexing_insert_batch_size: int = 100

    rate_limit_enabled: bool = True
    rate_limit_default_limit: int = 300
    rate_limit_default_window_seconds: int = 60
    rate_limit_rules: str = "/api/chat/query:20:60,/api/chat/voice:10:60,/api/chat/feedback:30:60,/api/admin/documents:30:60,/api/admin/reindex:10:60,/api/admin/stripe:10:60,/api/public/solicitudes-acceso:5:60"

    smtp_password: Optional[str] = None

    # Casilla de plataforma que recibe el aviso de cada solicitud de acceso.
    solicitudes_email: Optional[str] = None

    retrieval_similarity_threshold: float = 0.30
    retrieval_match_count: int = 4

    pii_anonymization_enabled: bool = False
    pii_mapping_retention_days: int = 90
    pii_nlp_model: str = "es_core_news_md"
    pii_language: str = "es"

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
