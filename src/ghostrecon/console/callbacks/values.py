import json
from typing import Any

from dash import ctx, html, no_update

from ghostrecon.console.components import icon


def _success_notice(message: str) -> html.Div:
    return html.Div([icon("check-circle"), html.Span(message)], className="success-notice")


def _first_value(values: list[Any] | None) -> Any:
    for value in values or []:
        if value not in (None, ""):
            return value
    return None


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _csv(value: Any, *, none_values: bool = False) -> list[str]:
    ignored = {"none", "n/a", "na", "null"} if none_values else set()
    return [
        item.strip()
        for item in str(value or "").split(",")
        if item.strip() and item.strip().lower() not in ignored
    ]


def _path_tail(pathname: str | None, prefix: str) -> str:
    path = (pathname or "").rstrip("/")
    if not path.startswith(prefix):
        return ""
    return path.removeprefix(prefix).split("/", 1)[0]


def _datetime_value(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    if "T" in text and "+" not in text and not text.endswith("Z"):
        return f"{text}:00Z" if len(text) == 16 else f"{text}Z"
    return text


def _dismissed_incidents(
    action_id: dict[str, Any], dismissed_incident_ids: list[str] | None
) -> Any:
    if action_id.get("kind") != "incident" or action_id.get("action") not in {
        "promote",
        "reject",
    }:
        return no_update
    target_id = str(action_id.get("target_id") or "")
    if not target_id:
        return no_update
    dismissed = [str(item) for item in dismissed_incident_ids or []]
    if target_id not in dismissed:
        dismissed.append(target_id)
    return dismissed


def _action_reason(action: str, extra_payload: dict[str, Any] | None) -> str:
    reason = str((extra_payload or {}).get("reason") or "").strip()
    return reason or f"Sprint 12 dashboard {action} action."


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1


def _version_map(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _triggered_click_count() -> int:
    triggered = getattr(ctx, "triggered", None) or []
    if not triggered:
        return 0
    value = triggered[0].get("value")
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
