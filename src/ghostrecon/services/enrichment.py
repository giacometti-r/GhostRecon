from collections.abc import Sequence

import dns.resolver
import httpx

from ghostrecon.models.api import DomainEnrichmentResult


async def enrich_domain(
    domain: str, security_signals: Sequence[dict[str, object]] = ()
) -> DomainEnrichmentResult:
    """Collect low-risk public domain metadata without paid APIs."""

    clean_domain = (
        domain.lower().strip().removeprefix("https://").removeprefix("http://").strip("/")
    )
    return DomainEnrichmentResult(
        domain=clean_domain,
        mx_records=_resolve_records(clean_domain, "MX"),
        nameservers=_resolve_records(clean_domain, "NS"),
        website_title=await _fetch_title(clean_domain),
        security_signals=list(security_signals),
    )


def _resolve_records(domain: str, record_type: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, record_type, lifetime=3)
    except Exception:
        return []
    return sorted(str(answer).rstrip(".") for answer in answers)


async def _fetch_title(domain: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            response = await client.get(f"https://{domain}")
            response.raise_for_status()
    except Exception:
        return None

    text = response.text[:200_000]
    lower = text.lower()
    start = lower.find("<title")
    if start == -1:
        return None
    start = lower.find(">", start)
    end = lower.find("</title>", start)
    if start == -1 or end == -1:
        return None
    return " ".join(text[start + 1 : end].split())[:255]
