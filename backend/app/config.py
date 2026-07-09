from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

# Look for .env in the project root (parent of backend/)
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    # Application
    app_name: str = "УмБаза"
    debug: bool = False
    cors_origins: list[str] = [
        "http://localhost:80",
        "http://localhost:3000",
        "http://localhost:8766",
        "http://localhost",
        "http://127.0.0.1:8766",
    ]

    # Database
    database_url: str = "postgresql+asyncpg://edusynth:edusynth@localhost:5432/edusynth"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return "postgresql+asyncpg://" + v[len("postgres://") :]
            if v.startswith("postgresql://"):
                return "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 2592000  # 30 days in seconds

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Guest access
    guest_lesson_limit: int = 1
    ai_provider: str = "yandex"  # "yandex" or "groq"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Yandex AI Studio
    yandex_folder_id: str = ""
    yandex_api_key: str = ""
    yandex_gpt_model: str = "yandexgpt"
    yandex_art_model: str = "yandexart"
    yandex_gpt_temperature: float = 0.7
    yandex_gpt_max_tokens: int = 4000

    # Image provider
    image_provider: str = "web_search"  # web_search | ai_svg | wikimedia | yandexart
    image_max_count: int = 3
    image_rehost_s3: bool = True
    image_candidate_pool: int = 25
    image_vision_shortlist: int = 10
    image_vision_verify: bool = True
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    # Yandex Object Storage (S3-compatible)
    s3_endpoint_url: str = "https://storage.yandexcloud.net"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "edusynth-images"
    s3_region: str = "ru-central1"

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
