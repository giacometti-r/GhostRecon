from typing import Any

from dash import dcc, html

from ghostrecon.console.api import (
    ConsoleApiClient,
)
from ghostrecon.console.components import (
    detail_panel,
    query_badges,
    records_table,
)

from .meeting_components import _attendees_display, _meeting_actions, _prep_packet_panel
from .shared import _filtered, _page, _pagination, _safe_get


def meetings_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div:
    payload = _safe_get(
        client,
        "/v1/reporting/meetings",
        _filtered(params, "status", "crm_sync_status", "cursor"),
    )
    children = [
        query_badges(params),
        records_table(
            payload.get("meetings", []),
            [
                ("Subject", "subject"),
                ("Status", "status"),
                ("Start", "start_at"),
                ("Calendar", "provider_event_id"),
                ("CRM sync", "crm_sync_status"),
                ("Outcome", "outcome_status"),
            ],
            actions=lambda record: [
                dcc.Link("Open", href=f"/meetings/{record.get('id')}", refresh=False)
            ],
        ),
        _pagination(payload, "/meetings", params),
    ]
    return _page("Meeting Handoff", [payload], children)


def meeting_detail_page(client: ConsoleApiClient, meeting_id: str, *, role: str) -> html.Div:
    payload = _safe_get(client, f"/v1/reporting/meetings/{meeting_id}")
    meeting = payload.get("meeting", {})
    children = [
        detail_panel(
            "Meeting detail",
            [
                ("Subject", meeting.get("subject")),
                ("Status", meeting.get("status")),
                ("Start", meeting.get("start_at")),
                ("End", meeting.get("end_at")),
                ("Timezone", meeting.get("timezone")),
                ("Attendees", _attendees_display(meeting.get("attendees"))),
                ("Calendar event", meeting.get("provider_event_id")),
                ("Calendar link", meeting.get("provider_html_link")),
                ("CRM sync", meeting.get("crm_sync_status")),
                ("CRM sync error", meeting.get("crm_sync_error")),
                ("Outcome", meeting.get("outcome_status")),
            ],
        ),
        html.Div(_meeting_actions(meeting, role), className="detail-actions"),
        _prep_packet_panel(meeting.get("prep_packet")),
        records_table(
            meeting.get("follow_up_tasks", []),
            [
                ("Title", "title"),
                ("Owner", "owner"),
                ("Due", "due_at"),
                ("Status", "status"),
                ("CRM sync", "crm_sync_status"),
            ],
        ),
    ]
    return _page("Meeting Detail", [payload], children)
