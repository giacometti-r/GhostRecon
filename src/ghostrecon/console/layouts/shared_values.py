import json
from typing import Any

from ghostrecon.console.components import (
    human_label,
)
from ghostrecon.models.api import DashboardRole


def _provenance_label(candidate: dict[str, Any]) -> str:
    origin = str(candidate.get("origin_type") or "")
    payload = candidate.get("candidate_payload") or {}
    if origin == "event_participant":
        return "Global events"
    if origin == "security_incident":
        return "Global incidents"
    if origin == "manual":
        actor = payload.get("created_by") or "unknown"
        return f"Manual by {actor}"
    return human_label(origin) if origin else "-"


def _clean_items(items: Any) -> list[Any]:
    if items in (None, "", []):
        return ["-"]
    if isinstance(items, list):
        return items or ["-"]
    return [items]


def _source_snapshot_rows(value: Any) -> list[Any]:
    if not isinstance(value, dict):
        return []
    return [
        {"label": human_label(key), "value": item}
        for key, item in value.items()
        if item not in (None, "", [], {})
    ]


def _inline_list(value: Any) -> str:
    if value in (None, ""):
        return "-"
    if isinstance(value, list):
        values = [str(item) for item in value if item not in (None, "")]
        return ", ".join(values) if values else "-"
    return str(value)


def _datetime_local_value(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    if "T" not in text:
        return text
    return text[:16]


def _action_id(
    kind: str,
    action: str,
    target_id: Any,
    version: Any = None,
    policy_hash: Any = None,
    enabled: Any = None,
) -> dict[str, Any]:
    return {
        "type": "dashboard-action",
        "kind": kind,
        "action": action,
        "target_id": str(target_id or ""),
        "version": _action_value(version),
        "policy_hash": policy_hash or "",
        "enabled": enabled if enabled is not None else "",
    }


def _action_value(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, str | int | float | bool):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def _can_mutate(role: str) -> bool:
    return role in {
        DashboardRole.ANALYST.value,
        DashboardRole.GOVERNANCE_REVIEWER.value,
        DashboardRole.ADMINISTRATOR.value,
    }


def _normalize_role(role: str | None) -> str:
    try:
        return DashboardRole(role or DashboardRole.VIEWER.value).value
    except ValueError:
        return DashboardRole.VIEWER.value
