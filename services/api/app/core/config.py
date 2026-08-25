from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ForgeOps AI API"
    app_version: str = "0.1.0"
    environment: str = "development"

    database_url: str
    redis_url: str

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    clerk_secret_key: str
    clerk_authorized_parties: str = "http://localhost:3000"

    s3_endpoint: str
    s3_public_endpoint: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "forgeops-documents"
    s3_presigned_url_expire_seconds: int = 900

    max_upload_size_bytes: int = 25 * 1024 * 1024

    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384

    gemini_api_key: str
    gemini_model: str = "gemini-3.7-flash"

    ingestion_queue_name: str = "forgeops:ingestion"
    worker_poll_timeout_seconds: int = 5
    worker_recovery_interval_seconds: int = 10
    worker_stale_job_seconds: int = 600
    worker_max_attempts: int = 3
    worker_retry_base_delay_seconds: int = 10
    worker_chunk_batch_size: int = 64

    # Agent / workflow runtime
    agent_model: str = "gemini-3.7-flash"
    agent_max_retrieval_candidates: int = 30
    agent_max_context_chunks: int = 8
    agent_thread_ttl_hours: int = 168
    langgraph_aes_key: str | None = None

    # GitHub action tool
    github_token: str | None = None
    github_api_base_url: str = "https://api.github.com"
    github_default_repository: str | None = None

    # Incident API tool
    incident_api_url: str | None = None
    incident_api_token: str | None = None

    # API hardening
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    # Optional observability
    otel_enabled: bool = False
    otel_service_name: str = "forgeops-api"
    otel_exporter_otlp_endpoint: str | None = None
    sentry_dsn: str | None = None
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def authorized_parties(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.clerk_authorized_parties.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()