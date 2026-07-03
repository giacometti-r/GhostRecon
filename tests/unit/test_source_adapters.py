from ghostrecon.services.source_adapters import (
    parse_gdelt_doc_articles,
    parse_http_page,
    parse_ics_events,
    parse_rss_atom,
    parse_schema_org_events,
)


def test_parse_http_page_extracts_metadata_without_body() -> None:
    item = parse_http_page(
        "<html><head><title>Security Event</title>"
        '<meta name="description" content="Annual security conference"></head></html>',
        "https://example.com/event",
        "en",
    )

    assert item.url == "https://example.com/event"
    assert item.content == "Security Event\nAnnual security conference"
    assert item.metadata["title"] == "Security Event"
    assert item.original_language == "en"


def test_parse_schema_org_events_extracts_event_json_ld() -> None:
    html = """
    <script type="application/ld+json">
      {"@context":"https://schema.org","@type":"Event","@id":"evt-1",
       "name":"DEF CON","url":"https://example.com/defcon","startDate":"2026-08-06"}
    </script>
    """

    items = parse_schema_org_events(html, "https://example.com", "en")

    assert len(items) == 1
    assert items[0].external_id == "evt-1"
    assert items[0].url == "https://example.com/defcon"
    assert "DEF CON" in items[0].content


def test_parse_ics_events_extracts_uid_and_summary() -> None:
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:event-1
SUMMARY:Security Summit
DESCRIPTION:Talks and workshops
URL:https://example.com/summit
END:VEVENT
END:VCALENDAR
"""

    items = parse_ics_events(ics, "https://example.com/calendar.ics")

    assert len(items) == 1
    assert items[0].external_id == "event-1"
    assert items[0].url == "https://example.com/summit"
    assert items[0].metadata["ics_event"]["SUMMARY"] == "Security Summit"


def test_parse_rss_atom_extracts_canonical_article_fields() -> None:
    feed = """<rss><channel><item>
      <title>Incident disclosed</title>
      <link>https://news.example/incident</link>
      <guid>article-1</guid>
      <pubDate>Fri, 26 Jun 2026 12:00:00 GMT</pubDate>
      <description>Company reports cyber incident</description>
    </item></channel></rss>"""

    items = parse_rss_atom(feed, "https://news.example/rss", "en")

    assert len(items) == 1
    assert items[0].external_id == "article-1"
    assert items[0].url == "https://news.example/incident"
    assert items[0].published_at is not None
    assert "Company reports" in items[0].content


def test_parse_gdelt_doc_articles_extracts_one_item_per_article_without_body() -> None:
    payload = """{
      "articles": [
        {
          "url": "https://news.example/breach",
          "title": "Example Corp reports ransomware incident",
          "seendate": "20260703T120000Z",
          "language": "English",
          "domain": "news.example",
          "sourcecountry": "US",
          "body": "full article body must not be retained"
        }
      ]
    }"""

    items = parse_gdelt_doc_articles(payload, "https://api.gdeltproject.org/api/v2/doc/doc")

    assert len(items) == 1
    assert items[0].url == "https://news.example/breach"
    assert items[0].published_at is not None
    assert items[0].metadata["gdelt_article"]["domain"] == "news.example"
    assert "body" not in items[0].metadata["gdelt_article"]
