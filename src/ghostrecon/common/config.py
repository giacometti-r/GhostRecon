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
    attio_read_rps: int = 80
    attio_write_rps: int = 20
    attio_events_list_api_slug: str = "ghostrecon-cyber-events"
    attio_event_participants_list_api_slug: str = "ghostrecon-event-participants"
    attio_incidents_list_api_slug: str = "ghostrecon-security-incidents"
    attio_companies_list_api_slug: str = "ghostrecon-companies"
    attio_incident_contacts_list_api_slug: str = "ghostrecon-incident-contacts"
    attio_meetings_list_api_slug: str = "ghostrecon-meetings"

    email_verifier_url: AnyHttpUrl = Field(default="http://email-verifier:8080")
    gateway_base_url: AnyHttpUrl = Field(default="http://gateway-service:8080")
    console_request_timeout_seconds: int = Field(default=10, ge=1)
    console_http_port: int = Field(default=8082, ge=1, le=65535)
    google_calendar_id: str | None = None
    google_client_email: str | None = None
    google_private_key: str | None = None
    google_delegated_subject: str | None = None
    google_calendar_send_updates: bool = True
    smtp_from_address: str = "prospecting@example.com"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    imap_host: str | None = None
    imap_port: int = 993
    imap_username: str | None = None
    imap_password: str | None = None
    imap_mailbox: str = "INBOX"
    sequence_domain_daily_limit: int = 50
    sequence_sender_daily_limit: int = 200
    sequence_channel_daily_limit: int = 500
    sequence_retry_after_seconds: int = 300
    crawl_user_agent: str = "GhostReconBot/0.1 (+https://example.com/bot)"
    crawl_respect_robots: bool = True
    crawl_max_pages_per_domain: int = 40
    crawl_max_depth: int = 2

    otel_exporter_otlp_endpoint: str | None = None
    metrics_namespace: str = "ghostrecon"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
