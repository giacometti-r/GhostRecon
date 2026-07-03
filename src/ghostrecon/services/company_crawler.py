import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.linkextractors import LinkExtractor
from scrapy.settings import Settings as ScrapySettings

CONTACT_TITLE_HINTS = re.compile(
    r"\b(ciso|cio|cto|vp|vice president|director|head of|security|risk|compliance|it)\b",
    re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


@dataclass(frozen=True)
class DiscoveredContact:
    full_name: str | None
    title: str | None
    email: str | None
    source_url: str
    confidence: int


class CompanyContactSpider(scrapy.Spider):
    """Scrapy spider for visible, allowlisted company contact pages."""

    name = "company_contact_spider"

    def __init__(
        self,
        *,
        domain: str,
        max_pages: int = 40,
        max_depth: int = 2,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.domain = domain.lower()
        self.allowed_domains = [self.domain]
        self.start_urls = [f"https://{self.domain}"]
        self.max_pages = max_pages
        self.max_depth = max_depth
        self._visited = 0
        self.link_extractor = LinkExtractor(
            allow_domains=self.allowed_domains,
            deny=(r"/privacy", r"/terms", r"/legal", r"/login", r"/signup"),
        )

    def parse(self, response: scrapy.http.Response) -> Iterable[dict[str, object]]:
        self._visited += 1
        yield from self._extract_contacts(response)

        depth = int(response.meta.get("depth", 0))
        if self._visited >= self.max_pages or depth >= self.max_depth:
            return

        for link in self.link_extractor.extract_links(response):
            if _is_promising_contact_url(link.url):
                yield response.follow(link.url, callback=self.parse)

    def _extract_contacts(self, response: scrapy.http.Response) -> Iterable[dict[str, object]]:
        text = " ".join(response.css("body ::text").getall())
        emails = sorted(set(EMAIL_PATTERN.findall(text)))
        title = _extract_title_hint(text)

        for email in emails:
            yield DiscoveredContact(
                full_name=None,
                title=title,
                email=email.lower(),
                source_url=response.url,
                confidence=70 if title else 50,
            ).__dict__


def build_scrapy_settings(user_agent: str, respect_robots: bool = True) -> ScrapySettings:
    return ScrapySettings(
        {
            "BOT_NAME": "ghostrecon",
            "USER_AGENT": user_agent,
            "ROBOTSTXT_OBEY": respect_robots,
            "AUTOTHROTTLE_ENABLED": True,
            "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
            "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
            "DOWNLOAD_TIMEOUT": 10,
            "DEPTH_LIMIT": 2,
            "LOG_LEVEL": "INFO",
            "TELNETCONSOLE_ENABLED": False,
        }
    )


def run_company_crawl(domain: str, user_agent: str, respect_robots: bool = True) -> None:
    process = CrawlerProcess(settings=build_scrapy_settings(user_agent, respect_robots))
    process.crawl(CompanyContactSpider, domain=domain)
    process.start()


def _is_promising_contact_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(
        hint in path
        for hint in (
            "about",
            "team",
            "leadership",
            "management",
            "contact",
            "security",
            "trust",
        )
    )


def _extract_title_hint(text: str) -> str | None:
    match = CONTACT_TITLE_HINTS.search(text)
    if not match:
        return None
    return match.group(0)
