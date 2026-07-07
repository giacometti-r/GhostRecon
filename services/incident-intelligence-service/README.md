
# incident-intelligence-service

## Purpose

Turns public incident/security articles and security feeds into incidents, watch targets, and governance-ready corroboration records. It owns incident candidate parsing, incident APIs, and watchlist APIs and should remain aligned with the implementation modules listed below.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=incident-intelligence-service`
- App construction: `ghostrecon.service_apps.factory.build_app` selects the router by service name.
- Health, middleware, and common settings come from the shared base app.

## Implementation Modules

- `src/ghostrecon/services/incident_intelligence.py`
- `src/ghostrecon/services/security_feeds.py`
- Related/shared: `src/ghostrecon/services/source_registry.py`

## APIs And Jobs

- `GET /v1/intelligence/incidents` via `intelligence_incidents` (service router).
- `GET /v1/intelligence/incidents/{incident_id}` via `intelligence_incident_detail` (service router).
- `GET /v1/intelligence/watch-targets` via `intelligence_watch_targets` (service router).
- `POST /v1/intelligence/watch-targets` via `intelligence_create_watch_target` (service router).
- `PATCH /v1/intelligence/watch-targets/{watch_target_id}` via `intelligence_patch_watch_target` (service router).
- `POST /v1/intelligence/incidents/{incident_id}/promote-to-watchlist` via `intelligence_promote_incident_to_watchlist` (service router).
- `GET /v1/intelligence/incidents` via `intelligence_incidents` (gateway).
- `GET /v1/intelligence/incidents/{incident_id}` via `intelligence_incident_detail` (gateway).
- `GET /v1/intelligence/watch-targets` via `intelligence_watch_targets` (gateway).
- `POST /v1/intelligence/watch-targets` via `intelligence_create_watch_target` (gateway).
- `PATCH /v1/intelligence/watch-targets/{watch_target_id}` via `intelligence_patch_watch_target` (gateway).
- `POST /v1/intelligence/incidents/{incident_id}/promote-to-watchlist` via `intelligence_promote_incident_to_watchlist` (gateway).
- Worker/helper entrypoint: `fetch_incident_source`.
- Worker/helper entrypoint: `parse_pending_incident_items`.

## Dependencies

- source registry definitions.
- raw source items.
- CISA KEV feed.
- NVD keyword search.

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
GHOSTRECON_SERVICE_NAME=incident-intelligence-service uvicorn ghostrecon.service_apps.runtime:app --reload --port 8080
```

## Verification

```bash
pytest tests/unit/test_incident_intelligence.py tests/unit/test_incident_routes.py
```
