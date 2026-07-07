
# ingestion-service

## Purpose

Owns source registration, duplicate detection, source adapter parsing, source health state, and fast webhook acknowledgement. It owns source registry, parser adapters, and webhook ingress and should remain aligned with the implementation modules listed below.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=ingestion-service`
- App construction: `ghostrecon.service_apps.factory.build_app` selects the router by service name.
- Health, middleware, and common settings come from the shared base app.

## Implementation Modules

- `src/ghostrecon/services/source_registry.py`
- `src/ghostrecon/services/source_adapters.py`
- Related/shared: `src/ghostrecon/service_apps/routers.py`

## APIs And Jobs

- `POST /webhooks/attio` via `attio_webhook` (service router).
- Worker/helper entrypoint: `source fetch workers call create_adapter and fetch_source_by_id`.

## Dependencies

- configured source definitions.
- raw source item table.
- Attio webhook secret.

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
GHOSTRECON_SERVICE_NAME=ingestion-service uvicorn ghostrecon.service_apps.runtime:app --reload --port 8080
```

## Verification

```bash
pytest tests/unit/test_source_registry.py tests/unit/test_source_adapters.py tests/unit/test_attio_signature.py
```
