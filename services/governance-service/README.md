# governance-service

## Purpose

`governance-service` owns source-reuse policy, incident corroboration decisions, suppression, lawful-basis metadata, retention, approval/rejection auditability, and inert CRM-target creation. It is the fail-closed policy boundary for contact enrichment, CRM export, and every outbound action.

Sprint 7 review approval creates a `CrmTarget` with `export_status=not_exported`. CRM export and outreach approval are separate decisions. Neither is implied by event/incident discovery.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=governance-service`

## Dependencies

- PostgreSQL source-policy, evidence, suppression, retention, review-decision, CRM-target, and audit tables.
- Event/incident intelligence services for source lineage and current canonical state.
- Console service for authenticated review workflows.
- CRM and sequencing services for enforcement at side-effect time.

## Operations

- Fail closed if reuse, corroboration, suppression, retention, lawful-basis, or approval state cannot be read.
- Require evidence and scope before setting participant reuse to `allowed`.
- Audit every approval, rejection, analyst corroboration, false-positive incident rejection, policy change, replay, suppression, and retention action.
- Invalidate eligibility when source policy, canonical identity, evidence, suppression, or material target data changes.
- Monitor blocked actions, policy-review expiry, approval age, suppression misses, replay count, and audit failures.

## APIs

- `POST /v1/suppressions`
- `POST /v1/suppressions/evaluate`
- `GET /v1/review/candidates`
- `GET /v1/review/crm-targets`
- `POST /v1/review/candidates/{candidate_id}/approve`
- `POST /v1/review/candidates/{candidate_id}/reject`
- `POST /v1/review/candidates/bulk-decision`
- `POST /v1/governance/incidents/{incident_id}/corroborate`
- `POST /v1/governance/incidents/{incident_id}/reject`

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=governance-service uvicorn ghostrecon.service_apps.runtime:app --reload
```

## Verification

```bash
pytest tests/unit/test_governance.py tests/unit/test_enrichment_routes.py
```
