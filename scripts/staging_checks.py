from __future__ import annotations

import asyncio
import json
import smtplib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx
from redis.asyncio import Redis

from ghostrecon.common.config import Settings, require_valid_configuration
from ghostrecon.services.calendar_adapters.google import GoogleCalendarClient

Check = Callable[[], Awaitable[None]]


async def _http_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> None:
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()


async def _checks(settings: Settings) -> dict[str, str]:
    async def database() -> None:
        from ghostrecon.common.database import check_database_schema_ready

        result = await check_database_schema_ready(settings)
        if not result.ready:
            raise RuntimeError("database readiness failed")

    async def redis() -> None:
        client = Redis.from_url(str(settings.redis_url))
        try:
            if not await client.ping():
                raise RuntimeError("Redis PING failed")
        finally:
            await client.aclose()

    async def attio() -> None:
        await _http_get(
            f"{str(settings.attio_base_url).rstrip('/')}/v2/self",
            headers={"Authorization": f"Bearer {settings.attio_access_token}"},
        )

    async def geocoder() -> None:
        await _http_get(
            f"{str(settings.nominatim_base_url).rstrip('/')}/search",
            headers={"User-Agent": settings.nominatim_user_agent},
            params={"q": "Zurich", "format": "jsonv2", "limit": "1"},
        )

    async def search() -> None:
        headers = (
            {"Authorization": f"Bearer {settings.openserp_api_key}"}
            if settings.openserp_api_key
            else None
        )
        await _http_get(
            f"{str(settings.openserp_base_url).rstrip('/')}/google/search",
            headers=headers,
            params={"text": "GhostRecon connectivity check", "limit": "1"},
        )

    async def news() -> None:
        await _http_get(
            str(settings.serpapi_base_url),
            params={
                "engine": "google_news",
                "q": "cybersecurity",
                "api_key": settings.serpapi_api_key or "",
                "num": "1",
            },
        )

    async def verifier() -> None:
        await _http_get(f"{str(settings.email_verifier_url).rstrip('/')}/api/status")

    async def google_calendar() -> None:
        await GoogleCalendarClient(settings)._token()

    async def smtp() -> None:
        def check() -> None:
            if not settings.smtp_host:
                raise RuntimeError("SMTP host missing")
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
                if settings.smtp_use_tls:
                    client.starttls()
                client.login(settings.smtp_username or "", settings.smtp_password or "")
                client.noop()

        await asyncio.to_thread(check)

    async def imap() -> None:
        import imaplib

        def check() -> None:
            if not settings.imap_host:
                raise RuntimeError("IMAP host missing")
            with imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port, timeout=10) as client:
                client.login(settings.imap_username or "", settings.imap_password or "")
                client.noop()

        await asyncio.to_thread(check)

    checks: dict[str, Check] = {
        "database": database,
        "redis": redis,
        "attio": attio,
        "geocoder": geocoder,
        "search": search,
        "news": news,
        "email_verifier": verifier,
        "google_calendar_auth": google_calendar,
        "smtp_noop": smtp,
        "imap_noop": imap,
    }
    evidence: dict[str, str] = {}
    for name, check in checks.items():
        try:
            await asyncio.wait_for(check(), timeout=20)
        except Exception as exc:
            evidence[name] = f"failed:{type(exc).__name__}"
        else:
            evidence[name] = "passed"
    return evidence


async def _main() -> int:
    settings = Settings()
    require_valid_configuration(settings)
    started = datetime.now(UTC)
    evidence = await _checks(settings)
    payload = {
        "profile": settings.profile.value,
        "service": settings.service_name.value,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "deadline_seconds": int(timedelta(minutes=5).total_seconds()),
        "checks": evidence,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if all(status == "passed" for status in evidence.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
