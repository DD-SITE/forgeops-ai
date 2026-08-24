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
    s3_region: str = "us-east-1"
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "forgeops-documents"
    s3_presigned_url_expire_seconds: int = 900

    max_upload_size_bytes: int = 25 * 1024 * 1024

    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384

    gemini_api_key: str
    gemini_model: str = "gemini-3.6-flash"

    ingestion_queue_name: str = "forgeops:ingestion"
    worker_poll_timeout_seconds: int = 5
    worker_recovery_interval_seconds: int = 10
    worker_stale_job_seconds: int = 600
    worker_max_attempts: int = 3
    worker_retry_base_delay_seconds: int = 10
    worker_chunk_batch_size: int = 64

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