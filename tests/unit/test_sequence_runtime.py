from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ghostrecon.common.config import Settings
from ghostrecon.models.api import (
    InboundEmailEventCreate,
    InboundEmailEventOut,
    InboundEmailEventType,
    SequenceEnrollmentList,
    SequenceEnrollmentOut,
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
    assert "approval_reason" in tables["sequence_enrollments"].columns
    assert "provider_message_id" in tables["outbound_emails"].columns


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

    async def fake_get(*args, **kwargs):
        return _enrollment()

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

    monkeypatch.setattr(routers, "create_sequence", fake_create_sequence)
    monkeypatch.setattr(routers, "create_sequence_enrollment", fake_create_enrollment)
    monkeypatch.setattr(routers, "list_sequence_enrollments", fake_list)
    monkeypatch.setattr(routers, "get_sequence_enrollment", fake_get)
    monkeypatch.setattr(routers, "pause_sequence_enrollment", fake_pause)
    monkeypatch.setattr(routers, "resume_sequence_enrollment", fake_resume)
    monkeypatch.setattr(routers, "cancel_sequence_enrollment", fake_cancel)
    monkeypatch.setattr(routers, "process_unsubscribe", fake_unsubscribe)

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

    assert sequence["steps"][0]["id"] == "step-1"
    assert enrollment["crm_target_id"] == "crm-target-1"
    assert listed["enrollments"][0]["id"] == "enrollment-1"
    assert detail["id"] == "enrollment-1"
    assert paused["status"] == "paused"
    assert resumed["status"] == "active"
    assert canceled["status"] == "canceled"
    assert unsubscribe["event_type"] == "unsubscribe"
    assert seen == {
        "sequence_name": "Incident follow-up",
        "sequence_key": "idem-sequence",
        "crm_target_id": "crm-target-1",
        "actor": "analyst@example.com",
        "list_status": "active",
        "unsubscribe_email": "ada@example.com",
        "unsubscribe_key": "idem-unsub",
    }


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
    assert "ghostrecon.retry_meeting_crm_sync" in celery_app.tasks
