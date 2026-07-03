# crm-service

## Purpose

`crm-service` exports analyst-approved GhostRecon intelligence targets to Attio first while preserving a provider-neutral `CrmClient` boundary. Attio is authoritative for approved sales records; GhostRecon remains authoritative for intelligence lineage, evidence, scoring, governance, review, and export audit state.

CRM ingestion/webhooks remain supported compatibility flows. They are not the primary acquisition path.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=crm-service`
- Attio env: `GHOSTRECON_ATTIO_BASE_URL`, `GHOSTRECON_ATTIO_ACCESS_TOKEN`

## Attio Target Mapping

- Custom `cyber_events` and `security_incidents` objects.
- Standard People and Companies records.
- Separate typed lists for events, event participants, incidents, affected companies, and incident contacts.
- Stable-identifier record upsert before list-entry creation.
- GhostRecon IDs and source-lineage summaries retained for reconciliation.

Exact mapping and lifecycle rules are in `docs/specifications/intelligence-pipeline.md`.

## Dependencies

- Governance/review state for current export eligibility.
- Attio REST API.
- PostgreSQL for `CrmExportBatch`, `CrmExportItem`, provider IDs, sync state, and audit events.
- Redis/Celery for dependency-ordered writes, retries, rate limits, and reconciliation.

## Operations

- Export only current analyst-approved typed targets.
- Treat every object/list write as idempotent and audit every attempt/outcome.
- Honor provider rate limits and isolate partial failures per item.
- Reconcile GhostRecon IDs, stable match keys, provider record IDs, and list-entry IDs.
- Never invoke sequence enrollment from an export.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=crm-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
