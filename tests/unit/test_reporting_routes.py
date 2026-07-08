from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from ghostrecon.common.config import Settings
from ghostrecon.models.api import (
    CrmTargetOut,
    CyberEventOut,
    DashboardRole,
    MeetingHandoffOut,
    ReportingCrmTargetList,
    ReportingEventDetail,
    ReportingEventList,
    ReportingIncidentDetail,
    ReportingIncidentList,
    ReportingKpiCatalog,
    ReportingMeetingDetail,
    ReportingMeetingList,
    ReportingMetadata,
    ReportingOperatorContext,
    ReportingReviewQueue,
    ReportingSourceHealthList,
    ReportingWatchTargetList,
    ReviewCandidateOut,
    SecurityIncidentOut,
    SourceHealth,
    SourceHealthStatus,
    WatchTargetOut,
)
from ghostrecon.service_apps import routers
from ghostrecon.service_apps.factory import build_app
from ghostrecon.services.reporting import (
    next_cursor,
    parse_cursor,
    project_crm_target,
    project_review_candidate,
    project_source_health,
    reporting_metadata_from_sources,
)

NOW = datetime(2026, 7, 6, tzinfo=UTC)


def _metadata(stale: bool = False) -> ReportingMetadata:
    return ReportingMetadata(
        generated_at=NOW,
        watermarks={"projection_generated_at": NOW},
        projection_version="reporting.v1.query",
        stale=stale,
        degraded_dependencies=["Delayed Source"] if stale else [],
    )


def _event() -> CyberEventOut:
    return CyberEventOut(
        id="event-1",
        name="DEF CON 34",
        event_series_key="def-con",
        confidence=90,
        created_at=NOW,
        updated_at=NOW,
    )


def _incident() -> SecurityIncidentOut:
    return SecurityIncidentOut(
        id="incident-1",
        title="Example Corp ransomware incident",
        confidence=75,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _watch_target() -> WatchTargetOut:
    return WatchTargetOut(
        id="watch-1",
        target_type="incident",
        canonical_target_key="incident-1",
        display_name="Example Corp ransomware incident",
        enabled=True,
        created_by="analyst@example.com",
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _review_candidate() -> ReviewCandidateOut:
    return ReviewCandidateOut(
        id="review-1",
        candidate_type="scoring",
        target_type="contact",
        target_id="contact-1",
        status="open",
        reason_code="score_requires_review",
        evidence_summary={"score": 60},
        policy_snapshot={"lawful_basis": "legitimate_interest"},
        policy_snapshot_hash="policy-hash",
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _crm_target() -> CrmTargetOut:
    return CrmTargetOut(
        id="crm-target-1",
        target_type="contact",
        target_id="contact-1",
        status="pending_export",
        export_status="not_exported",
        policy_snapshot={"lawful_basis": "legitimate_interest"},
        approval_snapshot={"actor": "analyst@example.com"},
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _meeting() -> MeetingHandoffOut:
    return MeetingHandoffOut(
        id="meeting-1",
        crm_target_id="crm-target-1",
        status="scheduled",
        subject="Security discovery",
        start_at=NOW,
        end_at=NOW,
        timezone="UTC",
        attendees=[{"email": "ada@example.com"}],
        calendar_provider="fake",
        provider_event_id="fake-meeting-1",
        crm_sync_status="pending",
        policy_snapshot={"lawful_basis": "legitimate_interest"},
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _source_health(status: SourceHealthStatus = SourceHealthStatus.FRESH) -> SourceHealth:
    return SourceHealth(
        source_definition_id="source-1",
        name="Example Source",
        source_kind="event",
        adapter_type="rss_atom",
        policy_state="allowed",
        participant_reuse_state="unknown",
        content_storage_policy="metadata_excerpt",
        enabled=True,
        operating_state="enabled",
        freshness_status=status,
        freshness_slo_seconds=3600,
        freshness_lag_seconds=120,
        checkpoint_state={"cursor": "abc"},
        last_success_at=NOW,
        last_error="selector failed" if status == SourceHealthStatus.DEGRADED else None,
    )


def test_reporting_routes_return_metadata_wrapped_contracts(monkeypatch) -> None:
    seen_roles: list[DashboardRole] = []

    async def fake_events(**kwargs):
        seen_roles.append(kwargs["operator"].role)
        return ReportingEventList(metadata=_metadata(), events=[_event()], next_cursor="1")

    async def fake_event_detail(*args, **kwargs):
        return ReportingEventDetail(metadata=_metadata(), event=_event())

    async def fake_incidents(**kwargs):
        return ReportingIncidentList(metadata=_metadata(), incidents=[_incident()])

    async def fake_incident_detail(*args, **kwargs):
        return ReportingIncidentDetail(metadata=_metadata(), incident=_incident())

    async def fake_watch_targets(**kwargs):
        return ReportingWatchTargetList(metadata=_metadata(), watch_targets=[_watch_target()])

    async def fake_review_queue(**kwargs):
        return ReportingReviewQueue(metadata=_metadata(), candidates=[_review_candidate()])

    async def fake_crm_targets(**kwargs):
        return ReportingCrmTargetList(metadata=_metadata(), crm_targets=[_crm_target()])

    async def fake_meetings(**kwargs):
        return ReportingMeetingList(metadata=_metadata(), meetings=[_meeting()])

    async def fake_meeting_detail(*args, **kwargs):
        return ReportingMeetingDetail(metadata=_metadata(), meeting=_meeting())

    async def fake_source_health(**kwargs):
        return ReportingSourceHealthList(metadata=_metadata(stale=True), sources=[_source_health()])

    async def fake_kpis(**kwargs):
        return ReportingKpiCatalog(
            metadata=_metadata(),
            kpis={"review": ["approval_rate"], "meeting_handoff": ["meetings_booked"]},
        )

    monkeypatch.setattr(routers, "get_reporting_events", fake_events)
    monkeypatch.setattr(routers, "get_reporting_event_detail", fake_event_detail)
    monkeypatch.setattr(routers, "get_reporting_incidents", fake_incidents)
    monkeypatch.setattr(routers, "get_reporting_incident_detail", fake_incident_detail)
    monkeypatch.setattr(routers, "get_reporting_watch_targets", fake_watch_targets)
    monkeypatch.setattr(routers, "get_reporting_review_queue", fake_review_queue)
    monkeypatch.setattr(routers, "get_reporting_crm_targets", fake_crm_targets)
    monkeypatch.setattr(routers, "get_reporting_meetings", fake_meetings)
    monkeypatch.setattr(routers, "get_reporting_meeting_detail", fake_meeting_detail)
    monkeypatch.setattr(routers, "get_reporting_source_health", fake_source_health)
    monkeypatch.setattr(routers, "get_reporting_kpi_catalog", fake_kpis)

    client = TestClient(build_app(Settings(service_name="reporting-service")))
    headers = {"X-Operator-Role": "analyst", "X-Actor": "analyst@example.com"}

    events = client.get("/v1/reporting/events?limit=1", headers=headers).json()
    event_detail = client.get("/v1/reporting/events/event-1", headers=headers).json()
    incidents = client.get("/v1/reporting/incidents", headers=headers).json()
    incident_detail = client.get("/v1/reporting/incidents/incident-1", headers=headers).json()
    watch_targets = client.get("/v1/reporting/watch-targets", headers=headers).json()
    review_queue = client.get("/v1/reporting/review-queue", headers=headers).json()
    crm_targets = client.get("/v1/reporting/crm-targets", headers=headers).json()
    meetings = client.get("/v1/reporting/meetings", headers=headers).json()
    meeting_detail = client.get("/v1/reporting/meetings/meeting-1", headers=headers).json()
    source_health = client.get("/v1/reporting/source-health", headers=headers).json()
    kpis = client.get("/v1/reporting/kpis/catalog", headers=headers).json()
    legacy_kpis = client.get("/v1/kpis/catalog", headers=headers).json()

    assert events["metadata"]["projection_version"] == "reporting.v1.query"
    assert events["next_cursor"] == "1"
    assert event_detail["event"]["id"] == "event-1"
    assert incidents["incidents"][0]["id"] == "incident-1"
    assert incident_detail["incident"]["id"] == "incident-1"
    assert watch_targets["watch_targets"][0]["origin_incident_id"] is None
    assert review_queue["candidates"][0]["evidence_summary"] == {"score": 60}
    assert crm_targets["crm_targets"][0]["export_status"] == "not_exported"
    assert meetings["meetings"][0]["provider_event_id"] == "fake-meeting-1"
    assert meeting_detail["meeting"]["subject"] == "Security discovery"
    assert source_health["metadata"]["stale"] is True
    assert kpis["kpis"]["review"] == ["approval_rate"]
    assert kpis["kpis"]["meeting_handoff"] == ["meetings_booked"]
    assert legacy_kpis["kpis"]["review"] == ["approval_rate"]
    assert seen_roles == [DashboardRole.ANALYST]


def test_reporting_rejects_unknown_operator_role() -> None:
    client = TestClient(build_app(Settings(service_name="reporting-service")))

    response = client.get("/v1/reporting/events", headers={"X-Operator-Role": "owner"})

    assert response.status_code == 403
    assert response.json()["detail"] == "unsupported operator role"


def test_reporting_cursor_helpers_are_offset_based_and_strict() -> None:
    assert parse_cursor(None) == 0
    assert parse_cursor("2") == 2
    assert next_cursor([object(), object()], limit=1, offset=2) == "3"
    assert next_cursor([object()], limit=1, offset=2) is None


def test_reporting_metadata_marks_stale_and_degraded_sources() -> None:
    metadata = reporting_metadata_from_sources(
        [_source_health(SourceHealthStatus.DEGRADED)],
        generated_at=NOW,
    )

    assert metadata.stale is True
    assert metadata.degraded_dependencies == ["Example Source"]
    assert metadata.watermarks["source_last_success_at"] == NOW


def test_reporting_role_projection_redacts_viewer_policy_detail() -> None:
    viewer = ReportingOperatorContext(role=DashboardRole.VIEWER)
    admin = ReportingOperatorContext(role=DashboardRole.ADMINISTRATOR)
    review = SimpleNamespace(
        id="review-1",
        candidate_type="scoring",
        target_type="contact",
        target_id="contact-1",
        origin_type=None,
        origin_id=None,
        source_definition_id=None,
        source_item_ids=[],
        status="open",
        reason_code="score_requires_review",
        reason="Detailed policy context.",
        evidence_summary={"score": 60},
        policy_snapshot={"lawful_basis": "legitimate_interest"},
        policy_snapshot_hash="policy-hash",
        sla_due_at=None,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    target = SimpleNamespace(
        id="crm-target-1",
        review_candidate_id=None,
        review_decision_id=None,
        target_type="contact",
        target_id="contact-1",
        origin_type=None,
        origin_id=None,
        source_definition_id=None,
        source_item_ids=[],
        status="pending_export",
        export_status="not_exported",
        policy_snapshot={"lawful_basis": "legitimate_interest"},
        approval_snapshot={"actor": "analyst@example.com"},
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    source = _source_health(SourceHealthStatus.DEGRADED)

    assert project_review_candidate(review, viewer).policy_snapshot == {}
    assert project_review_candidate(review, viewer).evidence_summary == {}
    assert project_crm_target(target, viewer).approval_snapshot == {}
    assert project_source_health(source, viewer).last_error is None
    assert project_review_candidate(review, admin).policy_snapshot == {
        "lawful_basis": "legitimate_interest"
    }
    assert project_source_health(source, admin).last_error == "selector failed"
