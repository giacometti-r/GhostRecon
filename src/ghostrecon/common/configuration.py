from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from ipaddress import ip_address
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

if TYPE_CHECKING:
    from ghostrecon.common.config import Settings


class RuntimeProfile(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class ServiceName(StrEnum):
    GATEWAY = "gateway-service"
    EVENT_INTELLIGENCE = "event-intelligence-service"
    INCIDENT_INTELLIGENCE = "incident-intelligence-service"
    ENRICHMENT = "enrichment-service"
    EMAIL_INTELLIGENCE = "email-intelligence-service"
    CRM = "crm-service"
    SEQUENCING = "sequencing-service"
    MEETING_HANDOFF = "meeting-handoff-service"
    SCORING_ROUTING = "scoring-routing-service"
    GOVERNANCE = "governance-service"
    REPORTING = "reporting-service"
    INGESTION = "ingestion-service"
    CONSOLE = "console-service"
    WORKER = "worker"
    SCHEDULER = "scheduler"
    MIGRATION = "migration-job"


class GeocoderProvider(StrEnum):
    NOMINATIM = "nominatim"
    LOCAL_DEMO = "local_demo"
    DISABLED = "disabled"


class SearchProviderName(StrEnum):
    OPENSERP = "openserp"
    LOCAL_DEMO = "local_demo"
    DISABLED = "disabled"


class NewsProviderName(StrEnum):
    SERPAPI = "serpapi"
    LOCAL_DEMO = "local_demo"
    DISABLED = "disabled"


class CrmProvider(StrEnum):
    ATTIO = "attio"
    LOCAL_DEMO = "local_demo"
    DISABLED = "disabled"


class CalendarProvider(StrEnum):
    GOOGLE = "google"
    FAKE = "fake"
    DISABLED = "disabled"


class EmailVerifierProvider(StrEnum):
    HTTP = "http"
    DISABLED = "disabled"


class SmtpProvider(StrEnum):
    SMTP = "smtp"
    DISABLED = "disabled"


class ImapProvider(StrEnum):
    IMAP = "imap"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ServiceRequirement:
    setting_name: str
    check_name: str
    credential: bool = False


DATABASE = ServiceRequirement("database_url", "database", credential=True)
REDIS = ServiceRequirement("redis_url", "redis", credential=True)
GATEWAY_URL = ServiceRequirement("gateway_base_url", "gateway")
GEOCODER = ServiceRequirement("geocoder_provider", "geocoder")
SEARCH = ServiceRequirement("search_provider", "search")
NEWS = ServiceRequirement("news_provider", "news")
VERIFIER = ServiceRequirement("email_verifier_provider", "email_verifier")
CRM = ServiceRequirement("crm_provider", "crm")
CALENDAR = ServiceRequirement("calendar_provider", "calendar")
SMTP = ServiceRequirement("smtp_provider", "smtp")
IMAP = ServiceRequirement("imap_provider", "imap")
CRAWLER = ServiceRequirement("crawl_user_agent", "crawler_identity")
ALL_LIVE_PROVIDERS = (GEOCODER, SEARCH, NEWS, VERIFIER, CRM, CALENDAR, SMTP, IMAP, CRAWLER)

SERVICE_REQUIREMENTS: dict[ServiceName, tuple[ServiceRequirement, ...]] = {
    ServiceName.GATEWAY: (DATABASE, *ALL_LIVE_PROVIDERS),
    ServiceName.EVENT_INTELLIGENCE: (DATABASE, GEOCODER),
    ServiceName.INCIDENT_INTELLIGENCE: (DATABASE, NEWS),
    ServiceName.ENRICHMENT: (DATABASE, SEARCH, VERIFIER, CRAWLER),
    ServiceName.EMAIL_INTELLIGENCE: (DATABASE, VERIFIER),
    ServiceName.CRM: (DATABASE, CRM),
    ServiceName.SEQUENCING: (DATABASE, CRM, SMTP, IMAP, CALENDAR),
    ServiceName.MEETING_HANDOFF: (DATABASE, CRM, CALENDAR),
    ServiceName.SCORING_ROUTING: (DATABASE,),
    ServiceName.GOVERNANCE: (DATABASE,),
    ServiceName.REPORTING: (DATABASE,),
    ServiceName.INGESTION: (DATABASE,),
    ServiceName.CONSOLE: (GATEWAY_URL,),
    ServiceName.WORKER: (DATABASE, REDIS, *ALL_LIVE_PROVIDERS),
    ServiceName.SCHEDULER: (REDIS,),
    ServiceName.MIGRATION: (DATABASE,),
}


@dataclass(frozen=True)
class ConfigurationIssue:
    profile: RuntimeProfile
    service: ServiceName
    setting_name: str
    error_code: str
    remediation: str

    def as_dict(self) -> dict[str, str]:
        return {
            "profile": self.profile.value,
            "service": self.service.value,
            "setting_name": self.setting_name,
            "error_code": self.error_code,
            "remediation": self.remediation,
        }


class ConfigurationValidationError(RuntimeError):
    def __init__(self, issues: list[ConfigurationIssue] | tuple[ConfigurationIssue, ...]) -> None:
        self.issues = tuple(issues)
        summary = "; ".join(
            f"{item.setting_name}: {item.error_code} ({item.remediation})" for item in self.issues
        )
        super().__init__(f"configuration validation failed: {summary}")


def requirements_for(service: ServiceName | str) -> tuple[ServiceRequirement, ...]:
    return SERVICE_REQUIREMENTS[ServiceName(service)]


def validate_configuration(
    settings: Settings, service: ServiceName | str | None = None
) -> tuple[ConfigurationIssue, ...]:
    selected = ServiceName(service or settings.service_name)
    if not settings.strict_runtime:
        return ()
    issues: list[ConfigurationIssue] = []
    required_names = {item.setting_name for item in requirements_for(selected)}

    def issue(name: str, code: str, remediation: str) -> None:
        issues.append(ConfigurationIssue(settings.profile, selected, name, code, remediation))

    for requirement in requirements_for(selected):
        value = getattr(settings, requirement.setting_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            issue(
                requirement.setting_name,
                "missing",
                f"set GHOSTRECON_{requirement.setting_name.upper()}",
            )

    providers: dict[str, StrEnum] = {
        "geocoder_provider": settings.geocoder_provider,
        "search_provider": settings.search_provider,
        "news_provider": settings.news_provider,
        "email_verifier_provider": settings.email_verifier_provider,
        "crm_provider": settings.crm_provider,
        "calendar_provider": settings.calendar_provider,
        "smtp_provider": settings.smtp_provider,
        "imap_provider": settings.imap_provider,
    }
    for name, provider in providers.items():
        if name in required_names and provider.value in {
            "disabled",
            "fake",
            "local_demo",
            "local-demo",
        }:
            issue(name, "non_live_provider", "select the supported live provider")

    credentials: dict[str, tuple[str, ...]] = {
        "news_provider": ("serpapi_api_key",),
        "crm_provider": ("attio_access_token",),
        "calendar_provider": ("google_calendar_id", "google_client_email", "google_private_key"),
        "smtp_provider": ("smtp_host", "smtp_username", "smtp_password", "smtp_from_address"),
        "imap_provider": ("imap_host", "imap_username", "imap_password"),
    }
    for owner, names in credentials.items():
        if owner not in required_names:
            continue
        for name in names:
            value = getattr(settings, name)
            if value is None or (isinstance(value, str) and not value.strip()):
                issue(name, "missing_credential", f"set GHOSTRECON_{name.upper()}")
            elif _is_placeholder(str(value)):
                issue(name, "placeholder", "replace the placeholder with a deployment secret")

    if "database_url" in required_names and _has_default_database_credentials(
        str(settings.database_url)
    ):
        issue("database_url", "default_credentials", "use non-default database credentials")
    if "database_url" in required_names and _dsn_has_placeholder(str(settings.database_url)):
        issue("database_url", "placeholder", "replace placeholder database credentials")
    if "redis_url" in required_names:
        redis_url = str(settings.redis_url)
        if _is_placeholder(redis_url) or _dsn_has_placeholder(redis_url):
            issue("redis_url", "placeholder", "configure a deployment Redis URL")
        elif urlsplit(redis_url).password is None:
            issue("redis_url", "default_credentials", "configure Redis authentication")

    public_urls = {
        "crm_provider": ("attio_base_url", settings.attio_base_url),
        "geocoder_provider": ("nominatim_base_url", settings.nominatim_base_url),
        "news_provider": ("serpapi_base_url", settings.serpapi_base_url),
    }
    service_urls = {
        "search_provider": ("openserp_base_url", settings.openserp_base_url),
        "email_verifier_provider": ("email_verifier_url", settings.email_verifier_url),
        "gateway_base_url": ("gateway_base_url", settings.gateway_base_url),
    }
    for owner, (name, url) in {**public_urls, **service_urls}.items():
        if owner not in required_names:
            continue
        parsed_url = urlsplit(str(url))
        if parsed_url.username is not None or parsed_url.password is not None:
            issue(name, "credential_bearing_url", "move credentials to an owned secret setting")
        if owner in public_urls and parsed_url.scheme != "https":
            issue(name, "insecure_public_url", "use an HTTPS provider endpoint")
        elif owner in service_urls and not _is_safe_service_url(str(url)):
            issue(name, "unsafe_url", "use HTTPS or an internal HTTP service URL")

    for name, owner in (
        ("nominatim_user_agent", "geocoder_provider"),
        ("crawl_user_agent", "crawl_user_agent"),
    ):
        if owner in required_names and not _is_identifying_user_agent(getattr(settings, name)):
            issue(
                name, "non_identifying_user_agent", "include a real operator URL or email address"
            )

    example_addresses = {
        "calendar_provider": ("google_client_email",),
        "smtp_provider": ("smtp_from_address", "smtp_username"),
        "imap_provider": ("imap_username",),
    }
    for owner, names in example_addresses.items():
        if owner not in required_names:
            continue
        for name in names:
            value = getattr(settings, name)
            if value and _is_example_address(value):
                issue(name, "example_address", "configure a real deployment address")

    if "calendar_provider" in required_names and settings.google_private_key:
        if not _is_rsa_private_key(settings.google_private_key):
            issue(
                "google_private_key",
                "malformed_private_key",
                "provide a PEM encoded RSA private key",
            )

    for name in required_names:
        value = getattr(settings, name)
        if isinstance(value, str) and _is_placeholder(value):
            issue(name, "placeholder", f"set a non-placeholder value for {name}")
    return tuple(_deduplicate(issues))


def require_valid_configuration(
    settings: Settings, service: ServiceName | str | None = None
) -> None:
    issues = validate_configuration(settings, service)
    if issues:
        raise ConfigurationValidationError(issues)


def assert_adapter_allowed(settings: Settings, adapter: object, capability: str) -> None:
    if not settings.strict_runtime:
        return
    identity = " ".join(
        str(part).lower()
        for part in (
            type(adapter).__name__,
            type(adapter).__module__,
            getattr(adapter, "provider", ""),
            getattr(adapter, "provider_name", ""),
        )
    )
    if any(
        marker in identity
        for marker in ("disabled", "fake", "localdemo", "local_demo", "local-demo")
    ):
        raise ConfigurationValidationError(
            [
                ConfigurationIssue(
                    settings.profile,
                    settings.service_name,
                    capability,
                    "synthetic_adapter",
                    "inject a live provider adapter",
                )
            ]
        )


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        not normalized
        or normalized.startswith("replace_")
        or normalized.startswith("replace-")
        or normalized in {"changeme", "change-me"}
    )


def _has_default_database_credentials(value: str) -> bool:
    parsed = urlsplit(value)
    return (parsed.username, parsed.password) in {
        ("ghostrecon", "ghostrecon"),
        ("postgres", "postgres"),
    }


def _dsn_has_placeholder(value: str) -> bool:
    parsed = urlsplit(value)
    return any(_is_placeholder(part or "") for part in (parsed.username, parsed.password))


def _is_example_address(value: str) -> bool:
    if "@" not in value:
        return False
    domain = value.rsplit("@", 1)[1].lower()
    return domain in {"example.com", "example.org", "example.net"} or domain.endswith(
        (".test", ".invalid")
    )


def _is_safe_service_url(value: str) -> bool:
    parsed = urlsplit(value)
    if parsed.scheme == "https":
        return True
    if parsed.scheme != "http" or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or "." not in host:
        return True
    if host.endswith((".internal", ".local", ".svc", ".cluster.local")):
        return True
    try:
        address = ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def _is_identifying_user_agent(value: str) -> bool:
    normalized = value.strip().lower()
    has_contact = "@" in normalized or "http://" in normalized or "https://" in normalized
    return bool(normalized) and has_contact and "example.com" not in normalized


def _is_rsa_private_key(value: str) -> bool:
    try:
        key = serialization.load_pem_private_key(value.replace("\\n", "\n").encode(), password=None)
    except (TypeError, ValueError):
        return False
    return isinstance(key, RSAPrivateKey)


def _deduplicate(issues: list[ConfigurationIssue]) -> list[ConfigurationIssue]:
    seen: set[tuple[str, str]] = set()
    result: list[ConfigurationIssue] = []
    for item in issues:
        key = (item.setting_name, item.error_code)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
