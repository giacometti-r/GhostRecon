
# crm-service

## Purpose

Plans and executes CRM exports, maps GhostRecon targets to Attio objects, tracks batch/item status, and retries failed export items. It owns CRM export batches, Attio adapter behavior, and CRM sync events and should remain aligned with the implementation modules listed below.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=crm-service`
- App construction: `ghostrecon.service_apps.factory.build_app` selects the router by service name.
- Health, middleware, and common settings come from the shared base app.

## Implementation Modules

- `src/ghostrecon/services/crm_exports.py`
- `src/ghostrecon/services/crm_attio.py`

## APIs And Jobs

- `POST /v1/crm/sync/account` via `crm_sync_account` (service router).
- `POST /v1/crm/exports` via `crm_export_start` (service router).
- `GET /v1/crm/exports/{batch_id}` via `crm_export_detail` (service router).
- `POST /v1/crm/exports/{batch_id}/retry-failed` via `crm_export_retry_failed` (service router).
- `POST /v1/crm/exports` via `crm_export_start` (gateway).
- `GET /v1/crm/exports/{batch_id}` via `crm_export_detail` (gateway).
- `POST /v1/crm/exports/{batch_id}/retry-failed` via `crm_export_retry_failed` (gateway).
- Worker/helper entrypoint: `process_crm_export_batch`.

## Dependencies

- CRM targets.
- Attio API token/workspace.
- outbox events.
- idempotency keys.

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
GHOSTRECON_SERVICE_NAME=crm-service uvicorn ghostrecon.service_apps.runtime:app --reload --port 8080
```

## Verification

```bash
pytest tests/unit/test_crm_exports.py
```
