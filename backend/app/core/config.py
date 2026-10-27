from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """12-factor config: every value comes from env / .env, nothing is hard-coded per environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "HelpdeskIQ"
    environment: str = "local"
    cors_origins: str = "http://localhost:5173"

    # Persistence. SQLite keeps local dev and tests dependency-free;
    # docker-compose / AWS point this at PostgreSQL (+ pgvector).
    database_url: str = "sqlite:///./helpdeskiq.db"
    redis_url: str | None = None          # cache + event stream; in-memory fallback when unset
    mongo_url: str | None = None          # chat transcripts / LLM audit log; SQL fallback when unset
    storage_dir: str = "./uploads"
    s3_bucket: str | None = None          # S3 / MinIO for uploaded documents
    s3_endpoint_url: str | None = None

    # Auth
    jwt_secret: str = "change-me-in-production-please-32b"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    frontend_url: str = "http://localhost:5173"

    # LLM gateway
    llm_provider: str = "claude"                    # claude | openai | azure_openai | mock
    llm_fallback_providers: str = "mock"            # comma separated, tried in order
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    # Model routing: a strong model for user-facing answers, a cheap one for classification.
    chat_model_claude: str = "claude-sonnet-5-5"
    fast_model_claude: str = "claude-haiku-5-5"
    chat_model_openai: str = "gpt-4o"
    fast_model_openai: str = "gpt-4o-mini"
    azure_chat_deployment: str = "gpt-4o"
    azure_fast_deployment: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    llm_cache_ttl_seconds: int = 3600
    llm_max_context_chunks: int = 4
    rate_limit_per_minute: int = 30

    # Events: Redis Streams when redis_url is set (separate worker process), otherwise an
    # in-process background thread. events_sync=True runs handlers inline (tests).
    events_sync: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
