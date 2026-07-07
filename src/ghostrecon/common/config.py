from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration shared by all microservices."""

    model_config = SettingsConfigDict(env_prefix="GHOSTRECON_", env_file=".env", extra="ignore")

    environment: Literal["local", "dev", "staging", "prod"] = "local"
    service_name: str = "gateway-service"
    log_level: str = "INFO"
    api_auth_token: str | None = None

    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://ghostrecon:ghostrecon@postgres:5432/ghostrecon"
    )
    redis_url: RedisDsn = Field(default="redis://redis:6379/0")

    attio_base_url: AnyHttpUrl = Field(default="https://api.attio.com")
    attio_access_token: str | None = None
    attio_webhook_secret: str | None = None
    attio_read_rps: int = 80
    attio_write_rps: int = 20
    attio_events_list_api_slug: str = "ghostrecon-cyber-events"
    attio_event_participants_list_api_slug: str = "ghostrecon-event-participants"
    attio_incidents_list_api_slug: str = "ghostrecon-security-incidents"
    attio_companies_list_api_slug: str = "ghostrecon-companies"
    attio_incident_contacts_list_api_slug: str = "ghostrecon-incident-contacts"

    email_verifier_url: AnyHttpUrl = Field(default="http://email-verifier:8080")
    smtp_from_address: str = "prospecting@example.com"
    crawl_user_agent: str = "GhostReconBot/0.1 (+https://example.com/bot)"
    crawl_respect_robots: bool = True
    crawl_max_pages_per_domain: int = 40
    crawl_max_depth: int = 2

    otel_exporter_otlp_endpoint: str | None = None
    metrics_namespace: str = "ghostrecon"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
