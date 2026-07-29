
# event-intelligence-service

## Purpose

Normalizes public cyber-event source data into searchable events and participant records for operators and downstream enrichment. It owns event intelligence ingestion, manual event create/edit workflows, event geocoding state, and event read APIs and should remain aligned with the implementation modules listed below.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=event-intelligence-service`
- App construction: `ghostrecon.service_apps.factory.build_app` selects the router by service name.
- Health, middleware, and common settings come from the shared base app.

## Implementation Modules

- `src/ghostrecon/services/event_intelligence/`
- `src/ghostrecon/services/geocoding.py`
- Related/shared: `src/ghostrecon/services/source_adapters.py`
- Related/shared: `src/ghostrecon/services/source_registry.py`

## APIs And Jobs

- `GET /v1/intelligence/sources/health` via `source_health` (service router).
- `GET /v1/intelligence/events` via `intelligence_events` (service router).
- `POST /v1/intelligence/events/manual` via `intelligence_create_manual_event` (service router).
- `PATCH /v1/intelligence/events/{event_id}` via `intelligence_patch_event` (service router).
- `GET /v1/intelligence/events/{event_id}` via `intelligence_event_detail` (service router).
- `GET /v1/intelligence/events/{event_id}/participants` via `intelligence_event_participants` (service router).
- `GET /v1/intelligence/participants` via `intelligence_participants` (service router).
- `GET /v1/intelligence/sources/health` via `source_health` (gateway).
- `GET /v1/intelligence/events` via `intelligence_events` (gateway).
- `POST /v1/intelligence/events/manual` via `intelligence_create_manual_event` (gateway).
- `PATCH /v1/intelligence/events/{event_id}` via `intelligence_patch_event` (gateway).
- `GET /v1/intelligence/events/{event_id}` via `intelligence_event_detail` (gateway).
- `GET /v1/intelligence/events/{event_id}/participants` via `intelligence_event_participants` (gateway).
- `GET /v1/intelligence/participants` via `intelligence_participants` (gateway).
- Worker/helper entrypoint: `fetch_event_source`.
- Worker/helper entrypoint: `parse_pending_event_items`.

## Dependencies

- source registry definitions.
- raw source items.
- event and participant persistence tables.
- geocoder configuration: `GHOSTRECON_GEOCODER_PROVIDER`, Nominatim base URL, and identifying Nominatim user agent when live geocoding is enabled.

## Operations

- Treat idempotency headers as required where route handlers declare `Idempotency-Key`.
- Preserve policy, lineage, and audit fields when backfilling or replaying data.
- Use service-specific routes for isolated deployment and gateway routes for aggregate API access.
- Prefer fixtures and fake adapters in local development; live providers should be explicit environment configuration.
- Store canonical event formats as `in-person`, `online`, `hybrid`, or `unknown`; `physical` and `virtual` remain accepted request/filter aliases.
- Live Nominatim-compatible geocoding uses structured address search with an identifying user agent and low request rate. Geocoding failures store status and must not block event creation.

## Failure Modes

- Invalid or conflicting workflow requests are surfaced as `409` or validation errors by route handlers.
- Missing records are surfaced as `404` on detail/action endpoints.
- Provider outages should degrade or retry according to the service implementation rather than bypassing policy gates.
- Database or outbox failures leave the operation incomplete and should be retried with the same idempotency key when available.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=event-intelligence-service uvicorn ghostrecon.service_apps.runtime:app --reload --port 8080
```

## Verification

```bash
pytest tests/unit/test_event_intelligence.py tests/unit/test_event_routes.py tests/unit/test_geocoding.py tests/unit/test_source_adapters.py tests/unit/test_source_registry.py
```

## Runtime configuration

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns database; live Nominatim geocoder and an identifying user agent. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Database-owning APIs verify the migrated schema; configured provider checks are named without exposing credentials.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
