from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Protocol
from urllib.parse import urlencode

import httpx
from defusedxml import ElementTree as ET

from ghostrecon.models.db import SourceDefinition


@dataclass(frozen=True)
class FetchedSourceItem:
    url: str
    content: str
    external_id: str | None = None
    published_at: datetime | None = None
    original_language: str | None = None
    source_timezone: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class SourceAdapter(Protocol):
    async def fetch(self, source: SourceDefinition) -> list[FetchedSourceItem]:
        """Fetch and parse items for a source definition."""


class HttpPageAdapter:
    async def fetch(self, source: SourceDefinition) -> list[FetchedSourceItem]:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(source.base_url)
            response.raise_for_status()
        return [parse_http_page(response.text, str(response.url), source.default_language)]


class SchemaOrgAdapter:
    async def fetch(self, source: SourceDefinition) -> list[FetchedSourceItem]:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(source.base_url)
            response.raise_for_status()
        return parse_schema_org_events(response.text, str(response.url), source.default_language)


class IcsAdapter:
    async def fetch(self, source: SourceDefinition) -> list[FetchedSourceItem]:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(source.base_url)
            response.raise_for_status()
        return parse_ics_events(response.text, str(response.url), source.default_language)


class RssAtomAdapter:
    async def fetch(self, source: SourceDefinition) -> list[FetchedSourceItem]:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(source.base_url)
            response.raise_for_status()
        return parse_rss_atom(response.text, str(response.url), source.default_language)


class ScheduledQueryAdapter:
    async def fetch(self, source: SourceDefinition) -> list[FetchedSourceItem]:
        params = source.query_scope.get("params", {})
        url = source.base_url
        if isinstance(params, dict) and params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(params, doseq=True)}"
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        metadata = {"query_scope": source.query_scope, "status_code": response.status_code}
        return [
            FetchedSourceItem(
                url=str(response.url),
                content=response.text,
                original_language=source.default_language,
                metadata=metadata,
            )
        ]


class GdeltDocAdapter:
    async def fetch(self, source: SourceDefinition) -> list[FetchedSourceItem]:
        raw_params = source.query_scope.get("params", {})
        params = {"mode": "artlist", "format": "json"}
        if isinstance(raw_params, dict):
            params.update(raw_params)
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(source.base_url, params=params)
            response.raise_for_status()
        return parse_gdelt_doc_articles(response.text, str(response.url), source.default_language)


def create_adapter(adapter_type: str) -> SourceAdapter:
    adapters: dict[str, SourceAdapter] = {
        "http_page": HttpPageAdapter(),
        "schema_org": SchemaOrgAdapter(),
        "ics": IcsAdapter(),
        "rss_atom": RssAtomAdapter(),
        "scheduled_query": ScheduledQueryAdapter(),
        "gdelt_doc": GdeltDocAdapter(),
    }
    try:
        return adapters[adapter_type]
    except KeyError as exc:
        raise ValueError(f"unsupported source adapter {adapter_type!r}") from exc


def parse_http_page(html: str, url: str, language: str | None = None) -> FetchedSourceItem:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = _compact_html_text(title_match.group(1)) if title_match else None
    description_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
        html,
        flags=re.IGNORECASE,
    )
    description = unescape(description_match.group(1)).strip() if description_match else ""
    content = "\n".join(part for part in (title, description) if part) or _compact_html_text(html)
    return FetchedSourceItem(
        url=url,
        content=content,
        original_language=language,
        metadata={"title": title, "description": description},
    )


def parse_schema_org_events(
    html: str, page_url: str, language: str | None = None
) -> list[FetchedSourceItem]:
    items: list[FetchedSourceItem] = []
    for script_body in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            payload = json.loads(unescape(script_body).strip())
        except json.JSONDecodeError:
            continue
        for event in _iter_jsonld_nodes(payload):
            node_type = event.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if "Event" not in types:
                continue
            event_url = event.get("url") or event.get("@id") or page_url
            name = str(event.get("name") or "").strip()
            description = str(event.get("description") or "").strip()
            content = "\n".join(part for part in (name, description) if part)
            items.append(
                FetchedSourceItem(
                    url=str(event_url),
                    content=content or json.dumps(event, sort_keys=True),
                    external_id=str(event.get("@id")) if event.get("@id") else None,
                    original_language=language,
                    metadata={"schema_org_event": event},
                )
            )
    return items


def parse_ics_events(
    ics_text: str, calendar_url: str, language: str | None = None
) -> list[FetchedSourceItem]:
    lines = _unfold_ics_lines(ics_text.splitlines())
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.split(";", 1)[0].upper()
        current[key] = value.strip()

    parsed: list[FetchedSourceItem] = []
    for event in events:
        summary = event.get("SUMMARY", "").strip()
        description = event.get("DESCRIPTION", "").strip()
        event_url = event.get("URL") or calendar_url
        content = "\n".join(part for part in (summary, description) if part)
        parsed.append(
            FetchedSourceItem(
                url=event_url,
                content=content or json.dumps(event, sort_keys=True),
                external_id=event.get("UID"),
                original_language=language,
                metadata={"ics_event": event},
            )
        )
    return parsed


def parse_rss_atom(
    feed_text: str, feed_url: str, language: str | None = None
) -> list[FetchedSourceItem]:
    try:
        root = ET.fromstring(feed_text)
    except ET.ParseError:
        return []

    candidates = list(root.findall(".//item")) or [
        element for element in root.iter() if _local_name(element.tag) == "entry"
    ]
    items: list[FetchedSourceItem] = []
    for entry in candidates:
        title = _child_text(entry, {"title"}) or ""
        description = _child_text(entry, {"description", "summary", "content"}) or ""
        link = _child_text(entry, {"link"}) or _link_href(entry) or feed_url
        guid = _child_text(entry, {"guid", "id"})
        published_raw = _child_text(entry, {"pubDate", "published", "updated"})
        items.append(
            FetchedSourceItem(
                url=link,
                content="\n".join(part for part in (title, description) if part),
                external_id=guid,
                published_at=_parse_feed_datetime(published_raw),
                original_language=language,
                metadata={
                    "feed_title": title,
                    "feed_description": description,
                    "published_raw": published_raw,
                },
            )
        )
    return items


def parse_gdelt_doc_articles(
    payload_text: str, query_url: str, language: str | None = None
) -> list[FetchedSourceItem]:
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return []
    articles = payload.get("articles", [])
    if not isinstance(articles, list):
        return []

    items: list[FetchedSourceItem] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        url = str(article.get("url") or "").strip()
        title = str(article.get("title") or "").strip()
        if not url or not title:
            continue
        snippet = str(article.get("snippet") or "").strip()
        published = _parse_feed_datetime(str(article.get("seendate") or ""))
        article_language = str(article.get("language") or language or "").strip() or language
        items.append(
            FetchedSourceItem(
                url=url,
                content="\n".join(part for part in (title, snippet) if part),
                external_id=str(article.get("url_mobile") or url),
                published_at=published,
                original_language=article_language,
                metadata={
                    "gdelt_article": {
                        key: value
                        for key, value in article.items()
                        if key.lower() not in {"body", "content", "html", "text"}
                    },
                    "query_url": query_url,
                },
            )
        )
    return items


def _iter_jsonld_nodes(payload: object) -> Iterable[dict[str, object]]:
    if isinstance(payload, dict):
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                if isinstance(item, dict):
                    yield item
        yield payload
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_jsonld_nodes(item)


def _unfold_ics_lines(lines: list[str]) -> list[str]:
    unfolded: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line.strip())
    return unfolded


def _child_text(element: ET.Element, names: set[str]) -> str | None:
    for child in element:
        if _local_name(child.tag) in names and child.text:
            return child.text.strip()
    return None


def _link_href(element: ET.Element) -> str | None:
    for child in element:
        if _local_name(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_feed_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


def _compact_html_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()
