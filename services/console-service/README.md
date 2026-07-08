
# console-service

## Purpose

Serves the Dash operator console, queries reporting/gateway APIs, renders pages, and dispatches governed operator actions. It owns Dash app shell, layouts, reusable components, API client, and action callbacks and should remain aligned with the implementation modules listed below.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=console-service`
- App construction: `ghostrecon.service_apps.factory.build_app` selects the router by service name.
- Health, middleware, and common settings come from the shared base app.
- Console-specific behavior: the Dash app is mounted at `/` only when this service name is selected.

## Implementation Modules

- `src/ghostrecon/console/app.py`
- `src/ghostrecon/console/api.py`
- `src/ghostrecon/console/components.py`
- `src/ghostrecon/console/layouts.py`
- `src/ghostrecon/console/callbacks.py`
- Related/shared: `src/ghostrecon/service_apps/factory.py`

## APIs And Jobs

- `GET /v1/review/candidates` via `review_candidates` (service router).
- `POST /v1/review/candidates/{candidate_id}/approve` via `review_candidate_approve` (service router).
- `POST /v1/review/candidates/{candidate_id}/reject` via `review_candidate_reject` (service router).
- `POST /v1/review/candidates/bulk-decision` via `review_candidates_bulk_decision` (service router).
- `GET /v1/review/crm-targets` via `review_crm_targets` (service router).
- `GET /v1/review/candidates` via `review_candidates` (gateway).
- `POST /v1/review/candidates/{candidate_id}/approve` via `review_candidate_approve` (gateway).
- `POST /v1/review/candidates/{candidate_id}/reject` via `review_candidate_reject` (gateway).
- `POST /v1/review/candidates/bulk-decision` via `review_candidates_bulk_decision` (gateway).
- `GET /v1/review/crm-targets` via `review_crm_targets` (gateway).

## Dependencies

- Dash.
- DashIconify.
- httpx.
- gateway/reporting APIs.
- dashboard role headers.

## Operations

- Treat idempotency headers as required where route handlers declare `Idempotency-Key`.
- Preserve policy, lineage, and audit fields when backfilling or replaying data.
- Use service-specific routes for isolated deployment and gateway routes for aggregate API access.
- Prefer fixtures and fake adapters in local development; live providers should be explicit environment configuration.
- Dashboard sidebar, detail, and pagination links route through Dash `dcc.Location`; the active sidebar item follows the current URL and highlights parent sections for detail routes.

## Failure Modes

- Invalid or conflicting workflow requests are surfaced as `409` or validation errors by route handlers.
- Missing records are surfaced as `404` on detail/action endpoints.
- Provider outages should degrade or retry according to the service implementation rather than bypassing policy gates.
- Database or outbox failures leave the operation incomplete and should be retried with the same idempotency key when available.
- Failed dashboard API reads render visible error notices with endpoint/status context instead of leaving the page looking frozen.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=console-service uvicorn ghostrecon.service_apps.runtime:app --reload --port 8080
```

## Verification

```bash
pytest tests/unit/test_console_dashboard.py
pytest tests/browser/test_console_navigation_playwright.py
```
