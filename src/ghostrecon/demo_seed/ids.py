from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

DEMO_NAMESPACE = "https://ghostrecon.local/demo/sprint-15"


def _seed_uuid(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{DEMO_NAMESPACE}/{name}"))


def _slug(value: str) -> str:
    return "-".join(part for part in value.lower().replace(".", " ").split() if part)


@dataclass(frozen=True)
class DemoSeedIds:
    fresh_source_definition_id: str = _seed_uuid("source/fresh-event-source")
    degraded_source_definition_id: str = _seed_uuid("source/degraded-incident-source")
    cyber_event_id: str = _seed_uuid("event/cloud-security-summit")
    secondary_cyber_event_id: str = _seed_uuid("event/identity-defense-forum")
    event_participant_id: str = _seed_uuid("event-participant/morgan-lee")
    secondary_event_participant_id: str = _seed_uuid("event-participant/samira-owens")
    tertiary_event_participant_id: str = _seed_uuid("event-participant/leo-martin")
    security_incident_id: str = _seed_uuid("incident/example-ransomware")
    secondary_incident_id: str = _seed_uuid("incident/contoso-ransomware")
    review_incident_id: str = _seed_uuid("incident/nimbus-phishing")
    watch_target_id: str = _seed_uuid("watch/example-industries")
    approve_review_candidate_id: str = _seed_uuid("review/approve-incident")
    reject_review_candidate_id: str = _seed_uuid("review/reject-incident")
    contact_review_candidate_id: str = _seed_uuid("review/contact-domain")
    email_review_candidate_id: str = _seed_uuid("review/email-verification")
    export_crm_target_id: str = _seed_uuid("crm-target/export-ready")
    retry_crm_target_id: str = _seed_uuid("crm-target/retry-demo")
    meeting_crm_target_id: str = _seed_uuid("crm-target/meeting-demo")
    crm_export_batch_id: str = _seed_uuid("crm-export-batch/retryable")
    crm_export_item_id: str = _seed_uuid("crm-export-item/retryable")
    account_id: str = _seed_uuid("account/example-industries")
    contact_id: str = _seed_uuid("contact/taylor-ng")
    entity_resolution_case_id: str = _seed_uuid("entity-resolution/example-industries")
    contact_candidate_id: str = _seed_uuid("contact-candidate/avery-patel")
    domain_review_contact_candidate_id: str = _seed_uuid("contact-candidate/domain-review")
    email_candidate_id: str = _seed_uuid("email-candidate/avery-patel")
    watch_monitoring_run_id: str = _seed_uuid("watch-monitoring/example-industries")
    sequence_id: str = _seed_uuid("sequence/incident-follow-up")
    sequence_step_id: str = _seed_uuid("sequence-step/initial")
    sequence_call_step_id: str = _seed_uuid("sequence-step/call")
    sequence_meeting_step_id: str = _seed_uuid("sequence-step/meeting")
    active_sequence_enrollment_id: str = _seed_uuid("sequence-enrollment/active")
    paused_sequence_enrollment_id: str = _seed_uuid("sequence-enrollment/paused")
    sequence_activity_id: str = _seed_uuid("sequence-activity/email-approval")
    meeting_handoff_id: str = _seed_uuid("meeting/security-discovery")
    meeting_prep_packet_id: str = _seed_uuid("meeting-prep/security-discovery")
    meeting_follow_up_task_id: str = _seed_uuid("meeting-follow-up/security-discovery")


DEMO_SEED_IDS = DemoSeedIds()


DEMO_SEED_REPORTING_RESOURCES = (
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
