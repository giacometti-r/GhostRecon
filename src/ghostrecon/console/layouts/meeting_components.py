from typing import Any

from dash import html

from ghostrecon.console.components import (
    action_button,
    empty_state,
    human_label,
    render_inline_value,
)

from .shared_values import _action_id, _can_mutate, _clean_items, _source_snapshot_rows


def _prep_packet_panel(packet: Any) -> html.Section:
    if not isinstance(packet, dict) or not packet:
        return html.Section(
            [html.H2("Prep packet"), empty_state("No prep packet yet.")],
            className="detail-panel",
        )
    sections = [
        ("Account context", [packet.get("account_summary")]),
        ("Contacts", packet.get("stakeholder_map") or []),
        ("Signals", packet.get("likely_security_priorities") or []),
        ("Recommended talk tracks", packet.get("suggested_questions") or []),
        ("Risks and incidents", packet.get("risks") or []),
        ("Events and source context", _source_snapshot_rows(packet.get("source_snapshot"))),
    ]
    return html.Section(
        [
            html.H2("Prep packet"),
            html.Div(
                [
                    html.Div(
                        [
                            html.H3(title),
                            html.Div(
                                [_prep_packet_value(item) for item in _clean_items(items)],
                                className="prep-section-body",
                            ),
                        ],
                        className="prep-section",
                    )
                    for title, items in sections
                ],
                className="prep-packet",
            ),
        ],
        className="detail-panel prep-panel",
    )


def _prep_packet_value(value: Any) -> html.Div:
    if isinstance(value, dict):
        if "label" in value and "value" in value:
            return html.Div(
                [
                    html.Strong(str(value["label"])),
                    html.Span(render_inline_value(value["value"])),
                ],
                className="prep-row",
            )
        return html.Div(
            [
                html.Span(
                    f"{human_label(key)}: {render_inline_value(item)}",
                    className="prep-chip",
                )
                for key, item in value.items()
                if item not in (None, "", [], {})
            ],
            className="prep-row",
        )
    return html.Div(str(value), className="prep-row")


def _meeting_actions(record: dict[str, Any], role: str) -> list[Any]:
    disabled = not _can_mutate(role)
    return [
        action_button(
            "Prep packet",
            _action_id("meeting", "prep", record.get("id")),
            "file-text",
            disabled=disabled,
        ),
        action_button(
            "Record outcome",
            _action_id("meeting", "outcome", record.get("id")),
            "clipboard-check",
            disabled=disabled,
        ),
        action_button(
            "Retry CRM",
            _action_id("meeting", "retry-sync", record.get("id")),
            "rotate-ccw",
            disabled=disabled,
        ),
        action_button(
            "Cancel",
            _action_id("meeting", "cancel", record.get("id")),
            "x",
            disabled=disabled,
            danger=True,
        ),
    ]


def _participant_rows(
    participants: list[dict[str, Any]],
    contact_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    queued_origin_ids = {
        str(candidate.get("origin_id"))
        for candidate in contact_candidates
        if candidate.get("origin_id")
    }
    return [
        {
            **participant,
            "enrichment_queued": str(participant.get("id")) in queued_origin_ids,
        }
        for participant in participants
    ]


def _attendees_display(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "-"
    attendees: list[str] = []
    for item in value:
        if isinstance(item, dict):
            email = str(item.get("email") or "").strip()
            name = str(item.get("display_name") or item.get("name") or "").strip()
            if name and email:
                attendees.append(f"{name} <{email}>")
            elif email:
                attendees.append(email)
            elif name:
                attendees.append(name)
        elif item not in (None, ""):
            attendees.append(str(item))
    return ", ".join(attendees) if attendees else "-"
