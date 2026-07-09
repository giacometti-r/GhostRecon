from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ghostrecon.common.config import Settings
from ghostrecon.models.api import (
    CrmProspectList,
    CrmProspectOut,
    InboundEmailEventCreate,
    InboundEmailEventOut,
    InboundEmailEventType,
    SequenceActivityList,
    SequenceActivityOut,
    SequenceEmailAlertOut,
    SequenceEnrollmentList,
    SequenceEnrollmentOut,
    SequenceList,
    SequenceOut,
    SequenceStepOut,
)
from ghostrecon.models.db import Base
from ghostrecon.service_apps import routers
from ghostrecon.service_apps.factory import build_app
from ghostrecon.services import sequencing

NOW = datetime(2026, 7, 7, tzinfo=UTC)


def _sequence() -> SequenceOut:
    return SequenceOut(
        id="sequence-1",
        name="Incident follow-up",
        owner_id="owner-1",
        channel="email",
        status="active",
        rate_limit_policy={},
        created_at=NOW,
        updated_at=NOW,
        steps=[
            SequenceStepOut(
                id="step-1",
                sequence_id="sequence-1",
                step_order=1,
                channel="email",
                delay_seconds=0,
                subject_template="Hello {contact_first_name}",
                body_template="Checking in.",
                active=True,
                created_at=NOW,
                updated_at=NOW,
            )
        ],
    )


def _enrollment(status: str = "active") -> SequenceEnrollmentOut:
    return SequenceEnrollmentOut(
        id="enrollment-1",
        sequence_id="sequence-1",
        crm_target_id="crm-target-1",
        contact_id="contact-1",
        account_id="account-1",
        sequence_name="Incident follow-up",
        contact_name="Ada Lovelace",
        contact_email="ada@example.test",
        account_name="Example Corp",
        account_domain="example.com",
        crm_target_summary="contact · contact-1",
        status=status,
        approval_actor="analyst@example.com",
        approval_reason="approved outreach",
        current_step_order=1,
        next_step_at=NOW,
        pause_reason=None,
        policy_snapshot={},
        version=1,
        created_at=NOW,
        updated_at=NOW,
        completed_at=None,
        outbound_emails=[],
    )


def _alert(status: str = "pending") -> SequenceEmailAlertOut:
    return SequenceEmailAlertOut(
        id="alert-1",
        enrollment_id="enrollment-1",
        recipient_email="analyst@example.com",
        subject="Reminder",
        body="Follow up with Ada.",
        send_at=NOW,
        status=status,
        actor="analyst@example.com",
        provider_message_id=None,
        last_error=None,
        sent_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _activity(status: str = "pending_approval", channel: str = "email") -> SequenceActivityOut:
    return SequenceActivityOut(
        id="activity-1",
        enrollment_id="enrollment-1",
        sequence_step_id="step-1",
        outbound_email_id="email-1" if channel == "email" else None,
        meeting_handoff_id="meeting-1" if channel == "google_meet" else None,
        sequence_id="sequence-1",
        sequence_name="Incident follow-up",
        contact_name="Ada Lovelace",
        contact_email="ada@example.test",
        account_name="Example Corp",
        step_order=1,
        channel=channel,
        status=status,
        due_at=NOW,
        approved_by=None,
        approved_at=None,
        completed_by=None,
        completed_at=None,
        metadata={"instructions": "Follow up"},
        created_at=NOW,
        updated_at=NOW,
    )


def _prospect() -> CrmProspectOut:
    return CrmProspectOut(
        provider_record_id="demo-crm-prospect-taylor-ng",
        provider_object="people",
        display_name="Taylor Ng",
        email="taylor.ng@example-industries.com",
        title="VP Security Operations",
        company_name="Example Industries",
        company_domain="example-industries.com",
    )


def _inbound_event() -> InboundEmailEventOut:
    return InboundEmailEventOut(
        id="event-1",
        enrollment_id="enrollment-1",
        outbound_email_id="email-1",
        event_type="unsubscribe",
        from_email="ada@example.com",
        to_email=None,
        message_id="msg-1",
        provider_payload={},
        occurred_at=NOW,
        created_at=NOW,
    )


def test_sprint_10_models_are_registered() -> None:
    tables = Base.metadata.tables

    assert "sequences" in tables
    assert "sequence_steps" in tables
    assert "sequence_enrollments" in tables
    assert "outbound_emails" in tables
    assert "inbound_email_events" in tables
    assert "sequence_suppression_events" in tables
    assert "sequence_email_alerts" in tables
    assert "sequence_step_activities" in tables
    assert "definition_version" in tables["sequences"].columns
    assert "definition_version" in tables["sequence_steps"].columns
    assert "requires_approval" in tables["sequence_steps"].columns
    assert "step_metadata" in tables["sequence_steps"].columns
    assert "definition_version" in tables["sequence_enrollments"].columns
    assert "approval_reason" in tables["sequence_enrollments"].columns
    assert "provider_message_id" in tables["outbound_emails"].columns
    assert "recipient_email" in tables["sequence_email_alerts"].columns


def test_sequence_routes_create_enroll_manage_and_unsubscribe(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def fake_create_sequence(request, **kwargs):
        seen["sequence_name"] = request.name
        seen["sequence_key"] = kwargs["idempotency_key"]
        return _sequence()

    async def fake_create_enrollment(request, **kwargs):
        seen["crm_target_id"] = request.crm_target_id
        seen["actor"] = kwargs["actor"]
        return _enrollment()

    async def fake_list(**kwargs):
        seen["list_status"] = kwargs["status"]
        return SequenceEnrollmentList(enrollments=[_enrollment()])

    async def fake_list_sequences(**kwargs):
        seen["sequence_list_status"] = kwargs["status"]
        return SequenceList(sequences=[_sequence()])

    async def fake_get(*args, **kwargs):
        return _enrollment()

    async def fake_get_sequence(*args, **kwargs):
        return _sequence()

    async def fake_update_sequence(sequence_id, request, **kwargs):
        seen["updated_sequence"] = sequence_id
        seen["updated_steps"] = len(request.steps or [])
        return _sequence()

    async def fake_pause(*args, **kwargs):
        return _enrollment("paused")

    async def fake_resume(*args, **kwargs):
        return _enrollment("active")

    async def fake_cancel(*args, **kwargs):
        return _enrollment("canceled")

    async def fake_unsubscribe(request, **kwargs):
        seen["unsubscribe_email"] = str(request.email)
        seen["unsubscribe_key"] = kwargs["idempotency_key"]
        return _inbound_event()

    async def fake_create_alert(enrollment_id, request, **kwargs):
        seen["alert_enrollment"] = enrollment_id
        seen["alert_actor"] = kwargs["actor"]
        return _alert()

    async def fake_list_activities(**kwargs):
        seen["activity_status"] = kwargs["status"]
        seen["activity_channel"] = kwargs["channel"]
        return SequenceActivityList(activities=[_activity()])

    async def fake_approve_activity(activity_id, request, **kwargs):
        seen["approved_activity"] = activity_id
        seen["approved_actor"] = kwargs["actor"]
        return _activity("completed")

    async def fake_complete_activity(activity_id, request, **kwargs):
        seen["completed_activity"] = activity_id
        return _activity("completed", "call")

    async def fake_schedule_activity(activity_id, request, **kwargs):
        seen["scheduled_activity"] = activity_id
        return _activity("scheduled", "google_meet")

    async def fake_search_prospects(**kwargs):
        seen["prospect_query"] = kwargs["query"]
        return CrmProspectList(prospects=[_prospect()], provider="local-demo")

    async def fake_import_prospect(request, **kwargs):
        seen["imported_prospect"] = request.provider_record_id
        seen["import_key"] = kwargs["idempotency_key"]
        return _enrollment()

    monkeypatch.setattr(routers, "create_sequence", fake_create_sequence)
    monkeypatch.setattr(routers, "create_sequence_enrollment", fake_create_enrollment)
    monkeypatch.setattr(routers, "list_sequence_enrollments", fake_list)
    monkeypatch.setattr(routers, "get_sequence_enrollment", fake_get)
    monkeypatch.setattr(routers, "list_sequences", fake_list_sequences)
    monkeypatch.setattr(routers, "get_sequence", fake_get_sequence)
    monkeypatch.setattr(routers, "update_sequence", fake_update_sequence)
    monkeypatch.setattr(routers, "pause_sequence_enrollment", fake_pause)
    monkeypatch.setattr(routers, "resume_sequence_enrollment", fake_resume)
    monkeypatch.setattr(routers, "cancel_sequence_enrollment", fake_cancel)
    monkeypatch.setattr(routers, "process_unsubscribe", fake_unsubscribe)
    monkeypatch.setattr(routers, "create_sequence_email_alert", fake_create_alert)
    monkeypatch.setattr(routers, "list_sequence_activities", fake_list_activities)
    monkeypatch.setattr(routers, "send_approved_sequence_email", fake_approve_activity)
    monkeypatch.setattr(routers, "complete_sequence_activity", fake_complete_activity)
    monkeypatch.setattr(routers, "schedule_sequence_meeting_activity", fake_schedule_activity)
    monkeypatch.setattr(routers, "search_crm_prospects", fake_search_prospects)
    monkeypatch.setattr(routers, "import_crm_prospect_to_sequence", fake_import_prospect)

    client = TestClient(build_app(Settings(service_name="sequencing-service")))
    headers = {"Idempotency-Key": "idem-sequence", "X-Actor": "analyst@example.com"}
    sequence = client.post(
        "/v1/sequences",
        headers=headers,
        json={
            "name": "Incident follow-up",
            "steps": [{"subject_template": "Hi", "body_template": "Body"}],
        },
    ).json()
    enrollment = client.post(
        "/v1/sequences/enrollments",
        headers=headers,
        json={
            "sequence_id": "sequence-1",
            "crm_target_id": "crm-target-1",
            "outreach_approved": True,
            "approval_reason": "approved outreach",
        },
    ).json()
    listed = client.get("/v1/sequences/enrollments?status=active").json()
    sequences = client.get("/v1/sequences?status=active").json()
    sequence_detail = client.get("/v1/sequences/sequence-1").json()
    sequence_update = client.patch(
        "/v1/sequences/sequence-1",
        json={
            "name": "Incident follow-up",
            "steps": [{"subject_template": "Hi again", "body_template": "Body"}],
        },
    ).json()
    detail = client.get("/v1/sequences/enrollments/enrollment-1").json()
    paused = client.post(
        "/v1/sequences/enrollments/enrollment-1/pause",
        json={"reason": "manual pause"},
    ).json()
    resumed = client.post(
        "/v1/sequences/enrollments/enrollment-1/resume",
        json={"reason": "resume"},
    ).json()
    canceled = client.post(
        "/v1/sequences/enrollments/enrollment-1/cancel",
        json={"reason": "cancel"},
    ).json()
    unsubscribe = client.post(
        "/v1/sequences/unsubscribe",
        headers={"Idempotency-Key": "idem-unsub"},
        json={"email": "ada@example.com"},
    ).json()
    alert = client.post(
        "/v1/sequences/enrollments/enrollment-1/alerts",
        headers=headers,
        json={
            "recipient_email": "analyst@example.com",
            "subject": "Reminder",
            "body": "Follow up.",
        },
    ).json()
    activities = client.get("/v1/sequences/activities?status=pending_approval&channel=email").json()
    prospects = client.get("/v1/sequences/crm-prospects?query=taylor").json()
    imported = client.post(
        "/v1/sequences/enrollments/import-crm-prospect",
        headers=headers,
        json={
            "provider_record_id": "demo-crm-prospect-taylor-ng",
            "sequence_id": "sequence-1",
            "outreach_approved": True,
            "approval_reason": "approved outreach",
        },
    ).json()
    approved_activity = client.post(
        "/v1/sequences/activities/activity-1/approve-email",
        json={"reason": "approved"},
    ).json()
    completed_activity = client.post(
        "/v1/sequences/activities/activity-1/complete",
        json={"reason": "called"},
    ).json()
    scheduled_activity = client.post(
        "/v1/sequences/activities/activity-1/schedule-meeting",
        json={
            "subject": "Security discovery",
            "start_at": NOW.isoformat(),
            "end_at": NOW.replace(hour=1).isoformat(),
        },
    ).json()

    assert sequence["steps"][0]["id"] == "step-1"
    assert sequences["sequences"][0]["id"] == "sequence-1"
    assert sequence_detail["name"] == "Incident follow-up"
    assert sequence_update["id"] == "sequence-1"
    assert enrollment["crm_target_id"] == "crm-target-1"
    assert listed["enrollments"][0]["id"] == "enrollment-1"
    assert listed["enrollments"][0]["contact_name"] == "Ada Lovelace"
    assert listed["enrollments"][0]["contact_email"] == "ada@example.test"
    assert detail["id"] == "enrollment-1"
    assert paused["status"] == "paused"
    assert resumed["status"] == "active"
    assert canceled["status"] == "canceled"
    assert unsubscribe["event_type"] == "unsubscribe"
    assert alert["status"] == "pending"
    assert activities["activities"][0]["id"] == "activity-1"
    assert prospects["prospects"][0]["provider_record_id"] == "demo-crm-prospect-taylor-ng"
    assert imported["id"] == "enrollment-1"
    assert approved_activity["status"] == "completed"
    assert completed_activity["channel"] == "call"
    assert scheduled_activity["channel"] == "google_meet"
    assert seen == {
        "sequence_name": "Incident follow-up",
        "sequence_key": "idem-sequence",
        "crm_target_id": "crm-target-1",
        "actor": "analyst@example.com",
        "list_status": "active",
        "sequence_list_status": "active",
        "updated_sequence": "sequence-1",
        "updated_steps": 1,
        "unsubscribe_email": "ada@example.com",
        "unsubscribe_key": "idem-unsub",
        "alert_enrollment": "enrollment-1",
        "alert_actor": "analyst@example.com",
        "activity_status": "pending_approval",
        "activity_channel": "email",
        "prospect_query": "taylor",
        "imported_prospect": "demo-crm-prospect-taylor-ng",
        "import_key": "idem-sequence",
        "approved_activity": "activity-1",
        "approved_actor": "system",
        "completed_activity": "activity-1",
        "scheduled_activity": "activity-1",
    }


def test_sequence_step_validation_allows_non_email_metadata() -> None:
    sequence = SequenceOut(
        id="sequence-2",
        name="Multi-channel",
        owner_id=None,
        channel="email",
        status="active",
        rate_limit_policy={},
        definition_version=2,
        created_at=NOW,
        updated_at=NOW,
        steps=[
            SequenceStepOut(
                id="step-call",
                sequence_id="sequence-2",
                step_order=1,
                channel="call",
                delay_seconds=3600,
                subject_template=None,
                body_template=None,
                requires_approval=False,
                step_metadata={"instructions": "Call security leader."},
                definition_version=2,
                active=True,
                created_at=NOW,
                updated_at=NOW,
            )
        ],
    )

    assert sequence.steps[0].channel == "call"
    assert sequence.steps[0].step_metadata["instructions"] == "Call security leader."


def test_sendable_contact_requires_verified_email_lawful_basis_and_no_suppression() -> None:
    contact = SimpleNamespace(
        email="ada@example.com",
        email_status="verified",
        lawful_basis="legitimate_interest",
        do_not_contact_flag=False,
    )
    sequencing._require_sendable_contact(contact)

    with pytest.raises(ValueError, match="verified"):
        sequencing._require_sendable_contact(
            SimpleNamespace(
                email="ada@example.com",
                email_status="needs_review",
                lawful_basis="legitimate_interest",
                do_not_contact_flag=False,
            )
        )
    with pytest.raises(ValueError, match="lawful basis"):
        sequencing._require_sendable_contact(
            SimpleNamespace(
                email="ada@example.com",
                email_status="verified",
                lawful_basis=None,
                do_not_contact_flag=False,
            )
        )


@pytest.mark.asyncio
async def test_rate_limit_blocks_domain_before_send() -> None:
    class FakeResult:
        def scalars(self):
            return [
                SimpleNamespace(
                    to_email="existing@example.com",
                    from_email="sender@example.com",
                )
            ]

    class FakeSession:
        async def execute(self, query):
            _ = query
            return FakeResult()

    reason = await sequencing._rate_limit_blocker(
        FakeSession(),
        to_email="new@example.com",
        from_email="sender@example.com",
        channel="email",
        sequence=SimpleNamespace(rate_limit_policy={"domain_daily_limit": 1}),
        settings=Settings(),
    )

    assert reason == "domain daily rate limit reached for example.com"


@pytest.mark.asyncio
async def test_poll_inbound_uses_fake_imap_poller(monkeypatch) -> None:
    seen: list[tuple[str, str]] = []

    class FakePoller:
        def poll(self, limit: int = 50):
            assert limit == 5
            return [
                InboundEmailEventCreate(
                    event_type=InboundEmailEventType.REPLY,
                    from_email="ada@example.com",
                    message_id="msg-1",
                )
            ]

    async def fake_process(event, *, idempotency_key, settings=None):
        _ = settings
        seen.append((event.event_type.value, idempotency_key))
        return _inbound_event().model_copy(update={"id": "reply-1", "event_type": "reply"})

    monkeypatch.setattr(sequencing, "process_inbound_email_event", fake_process)

    result = await sequencing.poll_inbound_email_events(
        limit=5,
        settings=Settings(),
        poller=FakePoller(),
    )

    assert result == {"processed": 1, "event_ids": ["reply-1"]}
    assert seen == [("reply", "inbound_email:reply:msg-1")]


def test_sequence_worker_tasks_are_registered() -> None:
    from ghostrecon.worker_runtime import celery_app

    assert "ghostrecon.process_due_sequence_steps" in celery_app.tasks
    assert "ghostrecon.poll_sequence_inbound_email" in celery_app.tasks
    assert "ghostrecon.process_due_sequence_email_alerts" in celery_app.tasks
    assert "ghostrecon.retry_meeting_crm_sync" in celery_app.tasks
