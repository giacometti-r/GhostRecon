from typing import Any

from ghostrecon.console.components import (
    format_duration,
)


def _sequence_enrollment_row(enrollment: dict[str, Any]) -> dict[str, Any]:
    return {
        **enrollment,
        "contact_name": enrollment.get("contact_name") or enrollment.get("contact_id"),
        "account_name": enrollment.get("account_name")
        or enrollment.get("account_domain")
        or enrollment.get("account_id"),
        "sequence_name": enrollment.get("sequence_name") or enrollment.get("sequence_id"),
    }


def _sequence_row(sequence: dict[str, Any]) -> dict[str, Any]:
    channels = sorted({str(step.get("channel") or "email") for step in sequence.get("steps") or []})
    return {
        **sequence,
        "step_count": len(sequence.get("steps") or []),
        "channels": ", ".join(channels) or "-",
    }


def _sequence_step_row(step: dict[str, Any]) -> dict[str, Any]:
    metadata = step.get("step_metadata") if isinstance(step.get("step_metadata"), dict) else {}
    instruction = (
        metadata.get("instructions")
        or metadata.get("call_script")
        or metadata.get("meeting_subject")
        or step.get("body_template")
        or "-"
    )
    return {
        **step,
        "delay_display": format_duration(step.get("delay_seconds")),
        "instruction_summary": instruction,
    }


def _sequence_activity_row(activity: dict[str, Any]) -> dict[str, Any]:
    return {
        **activity,
        "contact_name": activity.get("contact_name") or activity.get("contact_email") or "-",
        "account_name": activity.get("account_name") or "-",
    }
