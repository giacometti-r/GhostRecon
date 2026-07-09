from pathlib import Path
from uuid import UUID

import pytest

from ghostrecon.common.config import Settings
from ghostrecon.demo_seed import (
    DEMO_SEED_IDS,
    DEMO_SEED_REPORTING_RESOURCES,
    DemoSeedSafetyError,
    assert_demo_seed_allowed,
)


def test_demo_seed_ids_are_stable_uuid_strings() -> None:
    ids = DEMO_SEED_IDS.__dict__

    assert set(ids) == {
        "fresh_source_definition_id",
        "degraded_source_definition_id",
        "cyber_event_id",
        "event_participant_id",
        "security_incident_id",
        "secondary_incident_id",
        "review_incident_id",
        "watch_target_id",
        "approve_review_candidate_id",
        "reject_review_candidate_id",
        "contact_review_candidate_id",
        "email_review_candidate_id",
        "export_crm_target_id",
        "retry_crm_target_id",
        "meeting_crm_target_id",
        "crm_export_batch_id",
        "crm_export_item_id",
        "account_id",
        "contact_id",
        "entity_resolution_case_id",
        "contact_candidate_id",
        "domain_review_contact_candidate_id",
        "email_candidate_id",
        "watch_monitoring_run_id",
        "sequence_id",
        "sequence_step_id",
        "sequence_call_step_id",
        "sequence_meeting_step_id",
        "active_sequence_enrollment_id",
        "paused_sequence_enrollment_id",
        "meeting_handoff_id",
        "meeting_prep_packet_id",
        "meeting_follow_up_task_id",
    }
    assert all(str(UUID(value)) == value for value in ids.values())
    assert len(set(ids.values())) == len(ids)


def test_demo_seed_refuses_non_local_environments_by_default(monkeypatch) -> None:
    monkeypatch.delenv("GHOSTRECON_ALLOW_DEMO_SEED", raising=False)

    with pytest.raises(DemoSeedSafetyError):
        assert_demo_seed_allowed(Settings(environment="prod"))


def test_demo_seed_allows_explicit_non_local_override(monkeypatch) -> None:
    monkeypatch.setenv("GHOSTRECON_ALLOW_DEMO_SEED", "1")

    assert_demo_seed_allowed(Settings(environment="prod"))


def test_demo_seed_covers_demo_check_reporting_resources() -> None:
    assert DEMO_SEED_REPORTING_RESOURCES == (
        "source_definitions",
        "cyber_events",
        "event_participants",
        "security_incidents",
        "watch_targets",
        "watch_target_monitoring_runs",
        "entity_resolution_cases",
        "contact_enrichment_candidates",
        "email_candidates",
        "review_candidates",
        "crm_targets",
        "crm_export_batches",
        "crm_export_items",
        "accounts",
        "contacts",
        "sequences",
        "sequence_steps",
        "sequence_enrollments",
        "sequence_step_activities",
        "meeting_handoffs",
        "meeting_prep_packets",
        "meeting_follow_up_tasks",
    )


def test_makefile_exposes_demo_workflow_targets() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "demo-reset:" in makefile
    assert "demo-check:" in makefile
    assert "demo: demo-reset" in makefile
    assert "sh scripts/demo_check.sh" in makefile


def test_demo_check_script_covers_required_health_checks() -> None:
    script = Path("scripts/demo_check.sh").read_text(encoding="utf-8")

    for service in (
        "postgres",
        "redis",
        "gateway-service",
        "console-service",
        "worker",
        "scheduler",
        "email-verifier",
    ):
        assert service in script

    for table_name in DEMO_SEED_REPORTING_RESOURCES:
        assert table_name in script

    for endpoint in (
        "/healthz",
        "/readyz",
        "/v1/reporting/kpis/catalog",
        "/v1/reporting/events",
        "/v1/reporting/incidents",
        "/v1/reporting/watch-targets",
        "/v1/reporting/review-queue",
        "/v1/enrichment/contact-candidates",
        "/v1/reporting/crm-targets",
        "/v1/reporting/meetings",
        "/v1/reporting/meetings/$demo_meeting_id",
        "/v1/sequences/enrollments",
        "/v1/crm/exports/$demo_crm_export_batch_id",
        "/v1/reporting/source-health",
        "/_dash-dependencies",
    ):
        assert endpoint in script

    assert "redis-cli ping" in script
    assert "alembic_version" in script
    assert "demo:sprint15:meeting:security-discovery" in script
    assert "demo:sprint15:crm-export-batch:retryable" in script
