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