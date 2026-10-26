from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """服务配置；环境变量优先于 .env。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "edu-customer-service"
    app_version: str = "0.1.0"
    env: str = "dev"

    database_url: str = (
        "postgresql+psycopg://customer_service:customer_service"
        "@192.168.168.100:5432/edu_customer_service"
    )
    redis_url: str = "redis://192.168.168.100:6379/0"
    ai_service_url: str = "http://127.0.0.1:8002"
    ai_timeout_seconds: float = 90.0

    internal_service_token: str = "dev-only-internal-service-token-change-me"
    jwt_secret: str = "dev-only-jwt-secret-change-me-0123456789"
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 604800
    demo_auth_enabled: bool = True

    cors_origins: str = "http://localhost:5173"
    conversation_idle_minutes: int = 120

    merge_delay_ms: int = 800
    max_merge_delay_ms: int = 2000
    worker_poll_ms: int = 100
    turn_lease_seconds: int = 120
    max_attempts: int = 3
    retry_delay_seconds: int = 2
    history_limit: int = 20
    outbox_poll_seconds: float = 1.0
    outbox_max_attempts: int = 5
    handoff_sla_seconds: int = 120

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
