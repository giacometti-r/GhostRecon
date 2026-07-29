
# governance-service

## Purpose

Enforces suppression and review decisions, creates CRM targets from approved candidates, and records incident corroboration, rejection, or revert decisions. It owns policy gates, suppressions, review decisions, CRM target creation, and incident governance and should remain aligned with the implementation modules listed below.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=governance-service`
- App construction: `ghostrecon.service_apps.factory.build_app` selects the router by service name.
- Health, middleware, and common settings come from the shared base app.

## Implementation Modules

- `src/ghostrecon/services/governance/`

## APIs And Jobs

- `POST /v1/suppressions` via `suppression_create` (service router).
- `POST /v1/suppressions/evaluate` via `suppression_check` (service router).
- `GET /v1/review/candidates` via `review_candidates` (service router).
- `POST /v1/review/candidates/{candidate_id}/approve` via `review_candidate_approve` (service router).
- `POST /v1/review/candidates/{candidate_id}/reject` via `review_candidate_reject` (service router).
- `POST /v1/review/candidates/bulk-decision` via `review_candidates_bulk_decision` (service router).
- `GET /v1/review/crm-targets` via `review_crm_targets` (service router).
- `POST /v1/governance/incidents/{incident_id}/corroborate` via `governance_corroborate_incident` (service router).
- `POST /v1/governance/incidents/{incident_id}/reject` via `governance_reject_incident` (service router).
- `POST /v1/governance/incidents/{incident_id}/revert` via `governance_revert_incident` (service router).
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

## Dependencies

- review candidates.
- suppressions.
- CRM targets.
- security incidents.
- outbox events.

## Operations

- Treat idempotency headers as required where route handlers declare `Idempotency-Key`.
- Preserve policy, lineage, and audit fields when backfilling or replaying data.
- Use service-specific routes for isolated deployment and gateway routes for aggregate API access.
- Prefer fixtures and fake adapters in local development; live providers should be explicit environment configuration.
- Incident corroborate, reject, and revert requests are version-aware. Revert is valid only from `corroborated` back to `candidate`.

## Failure Modes

- Invalid or conflicting workflow requests are surfaced as `409` or validation errors by route handlers.
- Missing records are surfaced as `404` on detail/action endpoints.
- Provider outages should degrade or retry according to the service implementation rather than bypassing policy gates.
- Database or outbox failures leave the operation incomplete and should be retried with the same idempotency key when available.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=governance-service uvicorn ghostrecon.service_apps.runtime:app --reload --port 8080
```

## Verification

```bash
pytest tests/unit/test_governance.py
```

## Runtime configuration

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns database only. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Database-owning APIs verify the migrated schema; configured provider checks are named without exposing credentials.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
