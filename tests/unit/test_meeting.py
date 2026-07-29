from datetime import UTC, datetime

from fastapi.testclient import TestClient

from ghostrecon.common.config import Settings
from ghostrecon.models.api import (
    CalendarAvailabilityResult,
    MeetingFollowUpTaskOut,
    MeetingHandoffList,
    MeetingHandoffOut,
    MeetingPrepPacketOut,
    PrepPacketRequest,
)
from ghostrecon.models.db import Base
from ghostrecon.service_apps import routers
from ghostrecon.service_apps.factory import build_app
from ghostrecon.services.meeting import build_prep_packet

NOW = datetime(2026, 7, 7, 15, tzinfo=UTC)


def test_build_prep_packet_includes_stakeholders_and_signals() -> None:
    packet = build_prep_packet(
        PrepPacketRequest(
            account={"company_name": "ExampleCo"},
            contacts=[{"full_name": "Ada Lovelace", "title": "CISO"}],
            signals=[{"signal_type": "kev", "signal_topic": "Known exploited vulnerability"}],
        )
    )

    assert "ExampleCo" in packet.account_summary
    assert packet.stakeholder_map == ["Ada Lovelace - CISO"]
    assert packet.likely_security_priorities == ["Known exploited vulnerability"]


def _meeting(status: str = "scheduled") -> MeetingHandoffOut:
    return MeetingHandoffOut(
        id="meeting-1",
        crm_target_id="crm-target-1",
        sequence_enrollment_id="enrollment-1",
        account_id="account-1",
        contact_id="contact-1",
        status=status,
        subject="Security discovery",
        description="Discuss incident follow-up.",
        location="Google Meet",
        start_at=NOW,
        end_at=NOW.replace(hour=16),
        timezone="UTC",
        attendees=[{"email": "ada@example.com", "name": "Ada Lovelace", "optional": False}],
        calendar_provider="fake",
        calendar_id="fake-calendar",
        provider_event_id="fake-meeting-1",
        provider_html_link="https://calendar.google.com/fake/meeting-1",
        outcome_status="completed" if status == "completed" else None,
        outcome_notes="Validated project.",
        next_steps=["Send architecture notes"],
        crm_sync_status="succeeded",
        policy_snapshot={"lawful_basis": "legitimate_interest"},
        version=1,
        created_at=NOW,
        updated_at=NOW,
        prep_packet=MeetingPrepPacketOut(
            id="packet-1",
            meeting_id="meeting-1",
            account_summary="ExampleCo has 1 known stakeholders and 1 active signals.",
            stakeholder_map=["Ada Lovelace - CISO"],
            likely_security_priorities=["Known exploited vulnerability"],
            suggested_questions=["Which security initiatives are funded this quarter?"],
            risks=["Signal relevance needs human validation before use in messaging"],
            source_snapshot={"account_id": "account-1"},
            generated_by="analyst@example.com",
            created_at=NOW,
            updated_at=NOW,
        ),
        follow_up_tasks=[
            MeetingFollowUpTaskOut(
                id="task-1",
                meeting_id="meeting-1",
                title="Send packet",
                description=None,
                owner="analyst@example.com",
                due_at=None,
                status="open",
                crm_sync_status="succeeded",
                provider_task_id="attio-meeting-1",
                last_error=None,
                created_at=NOW,
                updated_at=NOW,
            )
        ],
    )


def test_sprint_11_models_are_registered() -> None:
    tables = Base.metadata.tables

    assert "meeting_handoffs" in tables
    assert "meeting_prep_packets" in tables
    assert "meeting_follow_up_tasks" in tables
    assert "provider_event_id" in tables["meeting_handoffs"].columns
    assert "source_snapshot" in tables["meeting_prep_packets"].columns
    assert "crm_sync_status" in tables["meeting_follow_up_tasks"].columns


def test_meeting_routes_cover_handoff_runtime(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def fake_availability(request, **kwargs):
        seen["availability_attendees"] = [str(attendee) for attendee in request.attendees]
        return CalendarAvailabilityResult(calendars={"ada@example.com": []}, provider="fake")

    async def fake_create(request, **kwargs):
        seen["create_subject"] = request.subject
        seen["create_key"] = kwargs["idempotency_key"]
        seen["actor"] = kwargs["actor"]
        return _meeting()

    async def fake_list(**kwargs):
        seen["list_status"] = kwargs["status"]
        return MeetingHandoffList(meetings=[_meeting()])

    async def fake_get(*args, **kwargs):
        return _meeting()

    async def fake_prep(*args, **kwargs):
        seen["prep_key"] = kwargs["idempotency_key"]
        return _meeting()

    async def fake_outcome(*args, **kwargs):
        seen["outcome_key"] = kwargs["idempotency_key"]
        return _meeting("completed")

    async def fake_cancel(*args, **kwargs):
        return _meeting("canceled")

    async def fake_retry(*args, **kwargs):
        return _meeting()

    monkeypatch.setattr(routers.meetings, "get_calendar_availability", fake_availability)
    monkeypatch.setattr(routers.meetings, "create_meeting", fake_create)
    monkeypatch.setattr(routers.meetings, "list_meetings", fake_list)
    monkeypatch.setattr(routers.meetings, "get_meeting", fake_get)
    monkeypatch.setattr(routers.meetings, "generate_meeting_prep_packet", fake_prep)
    monkeypatch.setattr(routers.meetings, "record_meeting_outcome", fake_outcome)
    monkeypatch.setattr(routers.meetings, "cancel_meeting", fake_cancel)
    monkeypatch.setattr(routers.meetings, "retry_meeting_crm_sync", fake_retry)

    client = TestClient(build_app(Settings(service_name="meeting-handoff-service")))
    headers = {"Idempotency-Key": "idem-meeting", "X-Actor": "analyst@example.com"}
    availability = client.post(
        "/v1/calendar/availability",
        json={
            "attendees": ["ada@example.com"],
            "time_min": NOW.isoformat(),
            "time_max": NOW.replace(hour=16).isoformat(),
        },
    ).json()
    created = client.post(
        "/v1/meetings",
        headers=headers,
        json={
            "crm_target_id": "crm-target-1",
            "sequence_enrollment_id": "enrollment-1",
            "subject": "Security discovery",
            "start_at": NOW.isoformat(),
            "end_at": NOW.replace(hour=16).isoformat(),
            "attendees": [{"email": "ada@example.com", "name": "Ada Lovelace"}],
        },
    ).json()
    listed = client.get("/v1/meetings?status=scheduled").json()
    detail = client.get("/v1/meetings/meeting-1").json()
    prep = client.post(
        "/v1/meetings/meeting-1/prep-packet",
        headers={"Idempotency-Key": "idem-prep", "X-Actor": "analyst@example.com"},
    ).json()
    outcome = client.post(
        "/v1/meetings/meeting-1/outcome",
        headers=headers,
        json={
            "outcome_status": "completed",
            "outcome_notes": "Validated project.",
            "next_steps": ["Send architecture notes"],
            "follow_up_tasks": [{"title": "Send packet", "owner": "analyst@example.com"}],
        },
    ).json()
    canceled = client.post(
        "/v1/meetings/meeting-1/cancel",
        json={"reason": "customer canceled"},
    ).json()
    retried = client.post("/v1/meetings/meeting-1/retry-sync").json()
    compatibility = client.post(
        "/v1/meetings/prep-packet",
        json={
            "account": {"company_name": "ExampleCo"},
            "contacts": [{"full_name": "Ada Lovelace", "title": "CISO"}],
            "signals": [{"signal_topic": "Known exploited vulnerability"}],
        },
    ).json()

    assert availability["provider"] == "fake"
    assert created["provider_event_id"] == "fake-meeting-1"
    assert listed["meetings"][0]["id"] == "meeting-1"
    assert detail["prep_packet"]["id"] == "packet-1"
    assert prep["prep_packet"]["generated_by"] == "analyst@example.com"
    assert outcome["status"] == "completed"
    assert canceled["status"] == "canceled"
    assert retried["crm_sync_status"] == "succeeded"
    assert "ExampleCo" in compatibility["account_summary"]
    assert seen == {
        "availability_attendees": ["ada@example.com"],
        "create_subject": "Security discovery",
        "create_key": "idem-meeting",
        "actor": "analyst@example.com",
        "list_status": "scheduled",
        "prep_key": "idem-prep",
        "outcome_key": "idem-meeting",
    }
