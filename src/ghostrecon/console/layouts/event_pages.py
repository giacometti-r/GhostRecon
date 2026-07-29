from typing import Any

from dash import dcc, html

from ghostrecon.console.api import (
    ConsoleApiClient,
)
from ghostrecon.console.components import (
    detail_panel,
    metadata_details,
    query_badges,
    records_table,
)
from ghostrecon.models.api import DashboardRole

from .event_components import _address, _event_map, _location
from .event_forms import _event_edit_modal, _manual_event_form
from .meeting_components import _participant_rows
from .participant_forms import _event_participant_form, _participant_enrich_form
from .review_components import _participant_actions
from .shared import _filter_panel, _filtered, _page, _pagination, _safe_get
from .shared_values import _inline_list


def events_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div:
    payload = _safe_get(
        client,
        "/v1/reporting/events",
        _filtered(params, "series", "source", "country", "event_format", "topic", "cursor"),
    )
    events = payload.get("events", [])
    children = [
        query_badges(params),
        _filter_panel(
            "/events",
            params,
            [
                ("series", "Series"),
                ("source", "Source"),
                ("country", "Country"),
                ("event_format", "Format"),
                ("topic", "Topic"),
            ],
        ),
        _event_map(events),
        _manual_event_form(role),
        records_table(
            events,
            [
                ("Name", "name"),
                ("Series", "event_series_key"),
                ("Starts", "starts_at_utc"),
                ("Format", "event_format"),
                ("Country", "country"),
            ],
            actions=lambda record: [
                dcc.Link("Open", href=f"/events/{record.get('id')}", refresh=False)
            ],
        ),
        _pagination(payload, "/events", params),
    ]
    return _page("Global Events", [payload], children)


def event_detail_page(client: ConsoleApiClient, event_id: str, *, role: str) -> html.Div:
    payload = _safe_get(client, f"/v1/reporting/events/{event_id}")
    participants = _safe_get(client, f"/v1/intelligence/events/{event_id}/participants")
    queued = _safe_get(
        client,
        "/v1/enrichment/contact-candidates",
        {"origin_type": "event_participant", "limit": 500},
    )
    event = payload.get("event", {})
    participant_rows = _participant_rows(
        participants.get("participants", []),
        queued.get("candidates", []),
    )
    children = [
        _event_edit_modal(event, role),
        detail_panel(
            "Event detail",
            [
                ("Name", event.get("name")),
                ("Series", event.get("event_series_key")),
                ("Original time", event.get("original_start")),
                ("UTC time", event.get("starts_at_utc")),
                ("Timezone", event.get("iana_timezone") or event.get("source_timezone")),
                ("Venue", event.get("venue_name")),
                ("Location", _location(event)),
                ("Address", _address(event)),
                ("Canonical URL", event.get("canonical_url")),
                ("Topics", _inline_list(event.get("topics"))),
                ("Source items", _inline_list(event.get("source_item_ids"))),
            ],
        ),
        _event_participant_form(event.get("id") or event_id, role),
        records_table(
            participant_rows,
            [
                ("Name", "published_name"),
                ("Organization", "organization"),
                ("Role", "published_role"),
                ("Reuse", "reuse_state"),
                ("Contact allowed", "contact_extraction_allowed"),
                ("CRM export allowed", "crm_export_allowed"),
            ],
            actions=lambda record: _participant_actions(record, role),
        ),
        _participant_enrich_form(event_id, role),
        metadata_details(payload)
        if role == DashboardRole.GOVERNANCE_REVIEWER.value
        else html.Div(),
    ]
    return _page("Event Detail", [payload], children)
