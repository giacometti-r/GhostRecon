
# gateway-service

## Purpose

Mounts the aggregate API surface and forwards gateway routes to the same implementation functions used by service-specific routers. It owns route aggregation, service map, HTTP error translation, and FastAPI app construction and should remain aligned with the implementation modules listed below.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=gateway-service`
- App construction: `ghostrecon.service_apps.factory.build_app` selects the router by service name.
- Health, middleware, and common settings come from the shared base app.

## Implementation Modules

- `src/ghostrecon/service_apps/routers/`
- `src/ghostrecon/service_apps/factory.py`
- `src/ghostrecon/service_apps/entrypoint.py`
- `src/ghostrecon/service_apps/runtime.py`

## APIs And Jobs

- `GET /v1/service-map` via `service_map` (gateway).
- `GET /v1/intelligence/sources/health` via `source_health` (gateway).
- `GET /v1/reporting/events` via `reporting_events` (gateway).
- `GET /v1/reporting/events/{event_id}` via `reporting_event_detail` (gateway).
- `GET /v1/reporting/incidents` via `reporting_incidents` (gateway).
- `GET /v1/reporting/incidents/{incident_id}` via `reporting_incident_detail` (gateway).
- `GET /v1/reporting/watch-targets` via `reporting_watch_targets` (gateway).
- `GET /v1/reporting/review-queue` via `reporting_review_queue` (gateway).
- `GET /v1/reporting/crm-targets` via `reporting_crm_targets` (gateway).
- `GET /v1/reporting/meetings` via `reporting_meetings` (gateway).
- `GET /v1/reporting/meetings/{meeting_id}` via `reporting_meeting_detail` (gateway).
- `GET /v1/reporting/source-health` via `reporting_source_health` (gateway).
- `GET /v1/reporting/kpis/catalog` via `reporting_kpi_catalog` (gateway).
- `GET /v1/intelligence/events` via `intelligence_events` (gateway).
- `POST /v1/intelligence/events/manual` via `intelligence_create_manual_event` (gateway).
- `PATCH /v1/intelligence/events/{event_id}` via `intelligence_patch_event` (gateway).
- `GET /v1/intelligence/events/{event_id}` via `intelligence_event_detail` (gateway).
- `GET /v1/intelligence/events/{event_id}/participants` via `intelligence_event_participants` (gateway).
- `GET /v1/intelligence/participants` via `intelligence_participants` (gateway).
- `GET /v1/intelligence/incidents` via `intelligence_incidents` (gateway).
- `POST /v1/intelligence/incidents/manual` via `intelligence_create_manual_incident` (gateway).
- `GET /v1/intelligence/incidents/{incident_id}` via `intelligence_incident_detail` (gateway).
- `GET /v1/intelligence/watch-targets` via `intelligence_watch_targets` (gateway).
- `POST /v1/intelligence/watch-targets` via `intelligence_create_watch_target` (gateway).
- `PATCH /v1/intelligence/watch-targets/{watch_target_id}` via `intelligence_patch_watch_target` (gateway).
- `POST /v1/intelligence/incidents/{incident_id}/promote-to-watchlist` via `intelligence_promote_incident_to_watchlist` (gateway).
- `POST /v1/crm/exports` via `crm_export_start` (gateway).
- `GET /v1/crm/exports/{batch_id}` via `crm_export_detail` (gateway).
- `POST /v1/crm/exports/{batch_id}/retry-failed` via `crm_export_retry_failed` (gateway).
- `POST /v1/enrichment/entity-resolutions` via `enrichment_create_entity_resolution` (gateway).
- `GET /v1/enrichment/entity-resolutions` via `enrichment_entity_resolutions` (gateway).
- `POST /v1/enrichment/contact-candidates` via `enrichment_create_contact_candidate` (gateway).
- `GET /v1/enrichment/contact-candidates` via `enrichment_contact_candidates` (gateway).
- `POST /v1/enrichment/event-participants/{participant_id}/enrich-target` via `enrichment_event_participant_enrich_target` (gateway).
- `POST /v1/email/candidates/persist` via `email_persist_candidates` (gateway).
- `POST /v1/email/verify-batch` via `email_verify_batch` (gateway).
- `POST /v1/scoring/candidates` via `candidate_score` (gateway).
- `POST /v1/sequences/evaluate` via `sequence_eligibility` (gateway).
- `POST /v1/sequences` via `sequence_create` (gateway).
- `POST /v1/sequences/enrollments` via `sequence_enrollment_create` (gateway).
- `GET /v1/sequences/enrollments` via `sequence_enrollment_list` (gateway).
- `GET /v1/sequences/enrollments/{enrollment_id}` via `sequence_enrollment_detail` (gateway).
- `POST /v1/sequences/enrollments/{enrollment_id}/pause` via `sequence_enrollment_pause` (gateway).
- `POST /v1/sequences/enrollments/{enrollment_id}/resume` via `sequence_enrollment_resume` (gateway).
- `POST /v1/sequences/enrollments/{enrollment_id}/cancel` via `sequence_enrollment_cancel` (gateway).
- `POST /v1/sequences/unsubscribe` via `sequence_unsubscribe` (gateway).
- `POST /v1/calendar/availability` via `calendar_availability` (gateway).
- `POST /v1/meetings` via `meeting_create` (gateway).
- `GET /v1/meetings` via `meeting_list` (gateway).
- `GET /v1/meetings/{meeting_id}` via `meeting_detail` (gateway).
- `POST /v1/meetings/{meeting_id}/prep-packet` via `meeting_generate_prep_packet` (gateway).
- `POST /v1/meetings/{meeting_id}/outcome` via `meeting_record_outcome` (gateway).
- `POST /v1/meetings/{meeting_id}/cancel` via `meeting_cancel` (gateway).
- `POST /v1/meetings/{meeting_id}/retry-sync` via `meeting_retry_sync` (gateway).
- `POST /v1/meetings/prep-packet` via `prep_packet` (gateway).
- `POST /v1/suppressions` via `suppression_create` (gateway).
- `POST /v1/suppressions/evaluate` via `suppression_check` (gateway).
- `GET /v1/review/candidates` via `review_candidates` (gateway).
- `POST /v1/review/candidates/{candidate_id}/approve` via `review_candidate_approve` (gateway).
- `POST /v1/review/candidates/{candidate_id}/reject` via `review_candidate_reject` (gateway).
- `POST /v1/review/candidates/bulk-decision` via `review_candidates_bulk_decision` (gateway).
- `GET /v1/review/crm-targets` via `review_crm_targets` (gateway).
- `POST /v1/governance/incidents/{incident_id}/corroborate` via `governance_corroborate_incident` (gateway).
- `POST /v1/governance/incidents/{incident_id}/reject` via `governance_reject_incident` (gateway).
- `POST /v1/governance/incidents/{incident_id}/revert` via `governance_revert_incident` (gateway).
- `GET /v1/kpis/catalog` via `kpi_catalog` (gateway).

## Dependencies

- all service modules.
- FastAPI.
- common Settings.
- service_name routing.

## Sprint 25a Security Boundary

The gateway currently aggregates existing in-process/service-router handlers; it is not yet the sole
authenticated reverse proxy. The shared perimeter applies transport bounds and, in staging or
production, rejects legacy caller identity headers and untrusted internal OBO/service-authorization
headers. Login, callback, session, logout, security-administration, and audit-query routes do not yet
exist. The initial operation registry is declarative and does not classify or enforce the full route
set. Existing actor/role parameters remain local/test compatibility behavior only. See the
[security foundation reference](../../docs/security-foundation.md).

## Operations

- Treat idempotency headers as required where route handlers declare `Idempotency-Key`.
- Preserve policy, lineage, and audit fields when backfilling or replaying data.
- Use service-specific routes for isolated deployment and gateway routes for aggregate API access.
- Prefer fixtures and fake adapters in local development; live providers should be explicit environment configuration.

## Failure Modes

- Invalid or conflicting workflow requests are surfaced as `409` or validation errors by route handlers.
- Missing records are surfaced as `404` on detail/action endpoints.
- Provider outages should degrade or retry according to the service implementation rather than bypassing policy gates.
- Database or outbox failures leave the operation incomplete and should be retried with the same idempotency key when available.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=gateway-service uvicorn ghostrecon.service_apps.runtime:app --reload --port 8080
```

## Verification

```bash
pytest tests/unit/test_event_routes.py tests/unit/test_incident_routes.py tests/unit/test_reporting_routes.py tests/unit/test_enrichment_routes.py
```

## Runtime configuration

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns database; live geocoder, search, news, email verifier, Attio CRM, Google Calendar, SMTP, IMAP, and crawler identity. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Database-owning APIs verify the migrated schema; configured provider checks are named without exposing credentials.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
