# crm-service Technical README

## Responsibilities

- Expose provider-neutral `CrmClient` operations for schema validation, record upsert, relationship/list insertion, retries, reconciliation, and meeting outcome/follow-up sync.
- Implement Attio mapping for custom events/incidents and standard People/Companies.
- Create dependency-ordered, idempotent `CrmExportBatch` and `CrmExportItem` state.
- Re-check approval, source reuse, suppression, retention, and optimistic version before executing each item.
- Consume Attio webhook/import compatibility events without making them the primary acquisition path.
- Publish export lifecycle events and preserve provider/GhostRecon identifiers.

## Interfaces

Implemented baseline:

- `POST /v1/crm/sync/account`
- Shared `AttioClient` in `ghostrecon.services.crm_attio`

Implemented Sprint 9 export interfaces:

- `POST /v1/crm/exports`
- `GET /v1/crm/exports/{batch_id}`
- `POST /v1/crm/exports/{batch_id}/retry-failed`

All mutations require authenticated actor, `Idempotency-Key`, approved selection snapshot, and audit context.

## Attio Rules

- Custom object slugs: `cyber_events`, `security_incidents`.
- Standard object slugs: People and Companies.
- Typed lists: events, event participants (People), incidents, affected companies (Companies), and incident contacts (People).
- Upsert Companies by normalized domain and People by eligible verified business email; never match People by name alone.
- Upsert dependent records before creating list entries/relationships.
- Store GhostRecon canonical IDs and bounded lineage/evidence URLs in mapped attributes.
- Contain Attio attribute/list names inside the adapter.

## Events

- `crm_export.batch_started`
- `crm_export.item_succeeded`
- `crm_export.item_failed`
- `crm_export.batch_completed`
- `crm.synced` for meeting handoff sync results

## Failure Modes

- Rate limit: honor `Retry-After`, persist retry time, and pause only the affected workspace queue.
- Partial failure: retain succeeded items and retry failed retryable items only.
- Approval/policy changed: mark item `skipped_policy` and audit; do not write.
- Schema drift: fail adapter validation before the batch performs dependent writes.
- Reconciliation mismatch: preserve both IDs/states and surface unresolved status for analyst action.

## Testing

- Mocked Attio object/list contract tests.
- `CrmClient` provider-conformance tests.
- Stable-identifier upsert and duplicate list-entry tests.
- Dependency order, idempotent retry, rate-limit, and partial-failure tests.
- Approval/policy invalidation and no-sequence-side-effect tests.
- Reconciliation drift and recovery tests.
