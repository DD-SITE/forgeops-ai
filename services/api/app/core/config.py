from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_name: str = "ForgeOps AI API"
    app_version: str = "0.1.0"
    environment: str = "development"

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: str

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # -------------------------------------------------------------------------
    # API
    # -------------------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # -------------------------------------------------------------------------
    # CORS / Clerk
    # -------------------------------------------------------------------------
    clerk_secret_key: str = ""
    clerk_authorized_parties: str = "http://localhost:3000"

    # -------------------------------------------------------------------------
    # S3 / MinIO
    #
    # Internal endpoint:
    # Used by API/worker containers.
    #
    # Public endpoint:
    # Used when generating presigned URLs consumed by the browser.
    # -------------------------------------------------------------------------
    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str = "http://localhost:9000"
    s3_region: str = "us-east-1"

    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"

    s3_bucket: str = "forgeops"

    s3_presigned_url_expire_seconds: int = 900

    # -------------------------------------------------------------------------
    # Gemini
    # -------------------------------------------------------------------------
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # -------------------------------------------------------------------------
    # Embeddings
    # -------------------------------------------------------------------------
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384

    # -------------------------------------------------------------------------
    # Ingestion queue
    # -------------------------------------------------------------------------
    ingestion_queue_name: str = "forgeops:ingestion"

    # -------------------------------------------------------------------------
    # Rate limiting
    # -------------------------------------------------------------------------
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    # -------------------------------------------------------------------------
    # Uploads
    # -------------------------------------------------------------------------
    max_upload_size_bytes: int = 50 * 1024 * 1024

    # -------------------------------------------------------------------------
    # Worker
    # -------------------------------------------------------------------------
    worker_chunk_batch_size: int = 32
    worker_poll_timeout_seconds: int = 5
    worker_retry_base_delay_seconds: int = 2
    worker_max_attempts: int = 3
    worker_recovery_interval_seconds: int = 30
    worker_stale_job_seconds: int = 900

    # -------------------------------------------------------------------------
    # GitHub integration
    # -------------------------------------------------------------------------
    github_token: str = ""
    github_api_base_url: str = "https://api.github.com"
    github_default_repository: str = ""

    # -------------------------------------------------------------------------
    # Incident integration
    # -------------------------------------------------------------------------
    incident_api_url: str = ""
    incident_api_token: str = ""

    # -------------------------------------------------------------------------
    # Agent / retrieval
    # -------------------------------------------------------------------------
    agent_max_context_chunks: int = 8
    agent_max_retrieval_candidates: int = 20

    # -------------------------------------------------------------------------
    # LangGraph
    # -------------------------------------------------------------------------
    langgraph_aes_key: str = ""

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------
    sentry_dsn: str = ""

    otel_enabled: bool = False
    otel_service_name: str = "forgeops-api"
    otel_exporter_otlp_endpoint: str = ""

    # -------------------------------------------------------------------------
    # Pydantic Settings configuration
    # -------------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Derived configuration
    # -------------------------------------------------------------------------
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