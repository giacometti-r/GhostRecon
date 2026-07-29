from typing import Any

from dash import State

from .common import SEQUENCE_LAYER_COUNT


def _sequence_step_payload(step: dict[str, Any]) -> dict[str, Any]:
    channel = step.get("channel") or "email"
    payload = {
        "step_order": step.get("step_order"),
        "delay_seconds": step.get("delay_seconds") or 0,
        "channel": channel,
        "requires_approval": step.get("requires_approval"),
        "step_metadata": step.get("step_metadata") or {},
    }
    if step.get("subject_template") is not None:
        payload["subject_template"] = step.get("subject_template")
    elif channel == "email":
        payload["subject_template"] = "Follow up"
    if step.get("body_template") is not None:
        payload["body_template"] = step.get("body_template")
    elif channel == "email":
        payload["body_template"] = "Checking in."
    return payload


def _sequence_layer_states(prefix: str) -> list[State]:
    states: list[State] = []
    for index in range(1, SEQUENCE_LAYER_COUNT + 1):
        states.extend(
            [
                State(f"{prefix}-step-{index}-channel", "value"),
                State(f"{prefix}-step-{index}-delay-days", "value"),
                State(f"{prefix}-step-{index}-subject", "value"),
                State(f"{prefix}-step-{index}-body", "value"),
                State(f"{prefix}-step-{index}-approval", "value"),
            ]
        )
    return states


def _sequence_steps_from_layers(values: list[Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for index in range(0, len(values), 5):
        chunk = values[index : index + 5]
        if len(chunk) < 5:
            continue
        channel, delay_days, subject, body, approval = chunk
        if not channel:
            continue
        try:
            delay_seconds = int(float(delay_days or 0) * 86400)
        except (TypeError, ValueError):
            delay_seconds = 0
        step_order = len(steps) + 1
        step: dict[str, Any] = {
            "step_order": step_order,
            "channel": channel,
            "delay_seconds": delay_seconds,
            "requires_approval": "yes" in (approval or []),
            "step_metadata": {},
        }
        if channel == "email":
            step["subject_template"] = subject or "Follow up"
            step["body_template"] = body or "Checking in."
        elif channel == "google_meet":
            step["step_metadata"] = {
                "meeting_subject": subject or "Security discovery",
                "instructions": body or "Schedule a discovery meeting.",
            }
        else:
            step["step_metadata"] = {"instructions": body or "Call and log next steps."}
        steps.append(_sequence_step_payload(step))
    return steps
