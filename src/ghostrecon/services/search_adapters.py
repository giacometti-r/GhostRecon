from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx
import tldextract

from ghostrecon.common.config import Settings

CONTACT_DISCOVERY_TITLES = (
    '"Head of Cybersecurity" OR "CISO" OR "Chief Information Security Officer" OR '
    '"CTO" OR "Chief Technology Officer"'
)


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str | None = None
    rank: int | None = None
    source: str | None = None
    published_at: str | None = None
    raw: dict[str, object] | None = None


class SearchProvider(Protocol):
    provider_name: str

    async def search(self, query: str, *, limit: int) -> list[SearchResult]:
        """Run a web search and return normalized organic results."""


class NewsProvider(Protocol):
    provider_name: str

    async def search_news(self, query: str, *, limit: int) -> list[SearchResult]:
        """Run a news search and return normalized article results."""


class DisabledSearchProvider:
    provider_name = "disabled"

    async def search(self, query: str, *, limit: int) -> list[SearchResult]:
        _ = query, limit
        return []


class DisabledNewsProvider:
    provider_name = "disabled"

    async def search_news(self, query: str, *, limit: int) -> list[SearchResult]:
        _ = query, limit
        return []


class LocalDemoSearchProvider:
    provider_name = "local_demo"

    async def search(self, query: str, *, limit: int) -> list[SearchResult]:
        company = _company_from_query(query)
        if "linkedin.com/in" in query:
            slug = _slug(company)
            return [
                SearchResult(
                    title=f"{company} CISO | LinkedIn",
                    url=f"https://www.linkedin.com/in/{slug}-ciso",
                    snippet=f"{company} Chief Information Security Officer profile.",
                    rank=1,
                    source="linkedin",
                    raw={"demo": True, "query": query},
                )
            ][:limit]
        domain = f"{_slug(company)}.test"
        return [
            SearchResult(
                title=f"{company} Official Website",
                url=f"https://www.{domain}/en",
                snippet=f"Official website for {company}.",
                rank=1,
                source="local_demo",
                raw={"demo": True, "query": query},
            )
        ][:limit]


class OpenSerpSearchProvider:
    provider_name = "openserp"

    def __init__(
        self,
        settings: Settings,
        client_factory: type[httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        self.base_url = str(settings.openserp_base_url).rstrip("/")
        self.api_key = settings.openserp_api_key
        self.client_factory = client_factory

    async def search(self, query: str, *, limit: int) -> list[SearchResult]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with self.client_factory(
            timeout=20,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get(
                f"{self.base_url}/google/search",
                params={"text": query, "limit": limit},
            )
            response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("results", []) if isinstance(payload, dict) else []
        return [
            _result_from_openserp(item)
            for item in raw_results[:limit]
            if isinstance(item, dict)
        ]


class LocalDemoNewsProvider:
    provider_name = "local_demo"

    async def search_news(self, query: str, *, limit: int) -> list[SearchResult]:
        company = _company_from_query(query)
        return [
            SearchResult(
                title=f"{company} appoints new CISO after security program review",
                url=f"https://news.local.demo/{_slug(company)}/new-ciso",
                snippet=f"Local demo news item for query: {query}",
                rank=1,
                source="local_demo_news",
                raw={"demo": True, "query": query},
            )
        ][:limit]


class SerpApiGoogleNewsProvider:
    provider_name = "serpapi"

    def __init__(
        self,
        settings: Settings,
        client_factory: type[httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        self.base_url = str(settings.serpapi_base_url)
        self.api_key = settings.serpapi_api_key
        self.client_factory = client_factory

    async def search_news(self, query: str, *, limit: int) -> list[SearchResult]:
        if not self.api_key:
            return []
        async with self.client_factory(timeout=20, follow_redirects=True) as client:
            response = await client.get(
                self.base_url,
                params={
                    "engine": "google_news",
                    "q": query,
                    "api_key": self.api_key,
                    "num": limit,
                },
            )
            response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("news_results", []) if isinstance(payload, dict) else []
        return [
            _result_from_serpapi(item)
            for item in raw_results[:limit]
            if isinstance(item, dict)
        ]


def search_provider_for_settings(settings: Settings) -> SearchProvider:
    if settings.search_provider == "openserp":
        return OpenSerpSearchProvider(settings)
    if settings.search_provider == "local_demo":
        return LocalDemoSearchProvider()
    return DisabledSearchProvider()


def news_provider_for_settings(settings: Settings) -> NewsProvider:
    if settings.news_provider == "serpapi":
        return SerpApiGoogleNewsProvider(settings)
    if settings.news_provider == "local_demo":
        return LocalDemoNewsProvider()
    return DisabledNewsProvider()


def linkedin_contact_query(company_name: str) -> str:
    return f'site:linkedin.com/in ({CONTACT_DISCOVERY_TITLES}) "{company_name}"'


def official_website_query(company_name: str) -> str:
    return f"{company_name} official website"


def watch_monitoring_queries(company_name: str) -> list[str]:
    quoted = f'"{company_name}"'
    return [
        f'{quoted} ("board of directors" OR "board member" OR director) change',
        f'{quoted} ("new CISO" OR "appointed CISO" OR "Chief Information Security Officer")',
        f'{quoted} ("new CTO" OR "appointed CTO" OR "Chief Technology Officer")',
        f'{quoted} ("new CIO" OR "appointed CIO" OR "Chief Information Officer")',
        f'{quoted} ("Head of Cybersecurity" OR "head of cyber security") appointed',
        f'{quoted} (cyberattack OR "cyber attack" OR ransomware OR "data breach")',
    ]


def registrable_domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    value = url.strip()
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    extracted = tldextract.extract(value)
    if not extracted.domain or not extracted.suffix:
        return None
    return f"{extracted.domain}.{extracted.suffix}".lower()


def is_suspicious_domain(domain: str | None) -> bool:
    if not domain:
        return True
    lowered = domain.lower()
    suspicious = {
        "facebook.com",
        "github.com",
        "linkedin.com",
        "wikipedia.org",
        "x.com",
        "twitter.com",
        "youtube.com",
    }
    return lowered in suspicious or lowered.endswith(".local")


def _result_from_openserp(item: dict[str, object]) -> SearchResult:
    position = item.get("position")
    rank = None
    if isinstance(position, dict):
        try:
            rank = int(position.get("absolute") or 0) or None
        except (TypeError, ValueError):
            rank = None
    try:
        rank = rank or int(item.get("rank") or 0) or None
    except (TypeError, ValueError):
        rank = None
    return SearchResult(
        title=str(item.get("title") or ""),
        url=str(item.get("url") or ""),
        snippet=str(item.get("snippet") or "") or None,
        rank=rank,
        source=str(item.get("engine") or "openserp"),
        raw=item,
    )


def _result_from_serpapi(item: dict[str, object]) -> SearchResult:
    source = item.get("source")
    source_name = source.get("name") if isinstance(source, dict) else source
    return SearchResult(
        title=str(item.get("title") or ""),
        url=str(item.get("link") or item.get("url") or ""),
        snippet=str(item.get("snippet") or "") or None,
        rank=_int_or_none(item.get("position")),
        source=str(source_name or "serpapi"),
        published_at=str(item.get("date") or "") or None,
        raw=item,
    )


def _company_from_query(query: str) -> str:
    parts = [part for part in query.split('"') if part.strip()]
    if len(parts) >= 2:
        return parts[-1].strip()
    text = query.replace("official website", "").strip()
    return text or "Demo Company"


def _slug(value: str) -> str:
    return "-".join(part for part in value.lower().split() if part) or "demo-company"


def _int_or_none(value: object) -> int | None:
    try:
        resolved = int(value or 0)
    except (TypeError, ValueError):
        return None
    return resolved or None
