from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from ghostrecon.common.configuration import (
    SERVICE_REQUIREMENTS,
    CalendarProvider,
    ConfigurationIssue,
    ConfigurationValidationError,
    CrmProvider,
    EmailVerifierProvider,
    GeocoderProvider,
    ImapProvider,
    NewsProviderName,
    RuntimeProfile,
    SearchProviderName,
    ServiceName,
    ServiceRequirement,
    SmtpProvider,
    require_valid_configuration,
    requirements_for,
    validate_configuration,
)

__all__ = [
    "CalendarProvider",
    "ConfigurationIssue",
    "ConfigurationValidationError",
    "CrmProvider",
    "EmailVerifierProvider",
    "GeocoderProvider",
    "ImapProvider",
    "NewsProviderName",
    "RuntimeProfile",
    "SERVICE_REQUIREMENTS",
    "SearchProviderName",
    "ServiceName",
    "ServiceRequirement",
    "Settings",
    "SmtpProvider",
    "get_settings",
    "require_valid_configuration",
    "requirements_for",
    "validate_configuration",
]


class Settings(BaseSettings):
    """Runtime configuration shared by all microservices."""

    model_config = SettingsConfigDict(env_prefix="GHOSTRECON_", env_file=".env", extra="forbid")

    profile: RuntimeProfile = RuntimeProfile.LOCAL
    environment: Literal[None] = Field(default=None, exclude=True, repr=False)
    service_name: ServiceName = ServiceName.GATEWAY
    log_level: str = "INFO"
    api_auth_token: str | None = Field(default=None, repr=False)

    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://ghostrecon:ghostrecon@postgres:5432/ghostrecon",
        repr=False,
    )
    redis_url: RedisDsn = Field(default="redis://redis:6379/0", repr=False)

    crm_provider: CrmProvider = CrmProvider.LOCAL_DEMO
    attio_base_url: AnyHttpUrl = Field(default="https://api.attio.com", repr=False)
    attio_access_token: str | None = Field(default=None, repr=False)
    attio_read_rps: int = 80
    attio_write_rps: int = 20
    attio_events_list_api_slug: str = "ghostrecon-cyber-events"
    attio_event_participants_list_api_slug: str = "ghostrecon-event-participants"
    attio_incidents_list_api_slug: str = "ghostrecon-security-incidents"
    attio_companies_list_api_slug: str = "ghostrecon-companies"
    attio_incident_contacts_list_api_slug: str = "ghostrecon-incident-contacts"
    attio_meetings_list_api_slug: str = "ghostrecon-meetings"

    email_verifier_provider: EmailVerifierProvider = EmailVerifierProvider.HTTP
    email_verifier_url: AnyHttpUrl = Field(default="http://email-verifier:8080", repr=False)
    gateway_base_url: AnyHttpUrl = Field(default="http://gateway-service:8080", repr=False)
    console_request_timeout_seconds: int = Field(default=10, ge=1)
    console_http_port: int = Field(default=8082, ge=1, le=65535)
    geocoder_provider: GeocoderProvider = GeocoderProvider.LOCAL_DEMO
    nominatim_base_url: AnyHttpUrl = Field(
        default="https://nominatim.openstreetmap.org", repr=False
    )
    nominatim_user_agent: str = "GhostRecon/0.1 (+https://example.com/ghostrecon)"
    search_provider: SearchProviderName = SearchProviderName.LOCAL_DEMO
    openserp_base_url: AnyHttpUrl = Field(default="http://openserp:7000", repr=False)
    openserp_api_key: str | None = Field(default=None, repr=False)
    search_result_limit: int = Field(default=5, ge=1, le=25)
    news_provider: NewsProviderName = NewsProviderName.LOCAL_DEMO
    serpapi_base_url: AnyHttpUrl = Field(default="https://serpapi.com/search", repr=False)
    serpapi_api_key: str | None = Field(default=None, repr=False)
    watch_monitoring_interval_seconds: int = Field(default=3600, ge=300)
    calendar_provider: CalendarProvider = CalendarProvider.FAKE
    google_calendar_id: str | None = None
    google_client_email: str | None = None
    google_private_key: str | None = Field(default=None, repr=False)
    google_delegated_subject: str | None = None
    google_calendar_send_updates: bool = True
    smtp_provider: SmtpProvider = SmtpProvider.DISABLED
    smtp_from_address: str = "prospecting@example.com"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = Field(default=None, repr=False)
    smtp_use_tls: bool = True
    imap_provider: ImapProvider = ImapProvider.DISABLED
    imap_host: str | None = None
    imap_port: int = 993
    imap_username: str | None = None
    imap_password: str | None = Field(default=None, repr=False)
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

    @property
    def strict_runtime(self) -> bool:
        return self.profile in {RuntimeProfile.STAGING, RuntimeProfile.PRODUCTION}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
