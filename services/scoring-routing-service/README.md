
# scoring-routing-service

## Purpose

Scores leads and enrichment candidates, snapshots scoring policy, routes candidates, and creates review requests when policy requires approval. It owns lead scoring, candidate scoring, policy blockers, and score events and should remain aligned with the implementation modules listed below.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=scoring-routing-service`
- App construction: `ghostrecon.service_apps.factory.build_app` selects the router by service name.
- Health, middleware, and common settings come from the shared base app.

## Implementation Modules

- `src/ghostrecon/services/scoring.py`

## APIs And Jobs

- `POST /v1/scoring/lead` via `lead_score` (service router).
- `POST /v1/scoring/candidates` via `candidate_score` (service router).
- `POST /v1/scoring/candidates` via `candidate_score` (gateway).

## Dependencies

- candidate score requests.
- database sessions.
- outbox events.
- review candidate table.

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
GHOSTRECON_SERVICE_NAME=scoring-routing-service uvicorn ghostrecon.service_apps.runtime:app --reload --port 8080
```

## Verification

```bash
pytest tests/unit/test_scoring.py
```
