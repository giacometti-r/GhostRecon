
# sequencing-service

## Purpose

Creates sequences and enrollments, sends due outbound messages, processes inbound replies/bounces/unsubscribes, and enforces outreach safety gates. It owns sequence lifecycle, SMTP/IMAP adapters, suppressions, and outbound/inbound email state and should remain aligned with the implementation modules listed below.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=sequencing-service`
- App construction: `ghostrecon.service_apps.factory.build_app` selects the router by service name.
- Health, middleware, and common settings come from the shared base app.

## Implementation Modules

- `src/ghostrecon/services/sequencing.py`
- `src/ghostrecon/services/sequence_adapters.py`

## APIs And Jobs

- `POST /v1/sequences/evaluate` via `sequence_eligibility` (service router).
- `POST /v1/sequences` via `sequence_create` (service router).
- `POST /v1/sequences/enrollments` via `sequence_enrollment_create` (service router).
- `GET /v1/sequences/enrollments` via `sequence_enrollment_list` (service router).
- `GET /v1/sequences/enrollments/{enrollment_id}` via `sequence_enrollment_detail` (service router).
- `POST /v1/sequences/enrollments/{enrollment_id}/pause` via `sequence_enrollment_pause` (service router).
- `POST /v1/sequences/enrollments/{enrollment_id}/resume` via `sequence_enrollment_resume` (service router).
- `POST /v1/sequences/enrollments/{enrollment_id}/cancel` via `sequence_enrollment_cancel` (service router).
- `POST /v1/sequences/unsubscribe` via `sequence_unsubscribe` (service router).
- `POST /v1/sequences/evaluate` via `sequence_eligibility` (gateway).
- `POST /v1/sequences` via `sequence_create` (gateway).
- `POST /v1/sequences/enrollments` via `sequence_enrollment_create` (gateway).
- `GET /v1/sequences/enrollments` via `sequence_enrollment_list` (gateway).
- `GET /v1/sequences/enrollments/{enrollment_id}` via `sequence_enrollment_detail` (gateway).
- `POST /v1/sequences/enrollments/{enrollment_id}/pause` via `sequence_enrollment_pause` (gateway).
- `POST /v1/sequences/enrollments/{enrollment_id}/resume` via `sequence_enrollment_resume` (gateway).
- `POST /v1/sequences/enrollments/{enrollment_id}/cancel` via `sequence_enrollment_cancel` (gateway).
- `POST /v1/sequences/unsubscribe` via `sequence_unsubscribe` (gateway).
- Worker/helper entrypoint: `process_due_sequence_steps`.
- Worker/helper entrypoint: `poll_inbound_email_events`.

## Dependencies

- CRM targets.
- contacts/accounts.
- suppressions.
- SMTP server.
- IMAP mailbox.
- outbox events.

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
GHOSTRECON_SERVICE_NAME=sequencing-service uvicorn ghostrecon.service_apps.runtime:app --reload --port 8080
```

## Verification

```bash
pytest tests/unit/test_sequence_eligibility.py tests/unit/test_sequence_runtime.py
```
