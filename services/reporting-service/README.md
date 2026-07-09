
# reporting-service

## Purpose

Projects operational read models for geocoded events, company-specific incidents, watch targets, review queues, CRM targets, source health, meetings, and KPI catalog views. It owns read-only operator reporting APIs and pagination/filter projections and should remain aligned with the implementation modules listed below.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=reporting-service`
- App construction: `ghostrecon.service_apps.factory.build_app` selects the router by service name.
- Health, middleware, and common settings come from the shared base app.

## Implementation Modules

- `src/ghostrecon/services/reporting.py`

## APIs And Jobs

- `GET /v1/intelligence/sources/health` via `source_health` (service router).
- `GET /v1/reporting/events` via `reporting_events` (service router).
- `GET /v1/reporting/events/{event_id}` via `reporting_event_detail` (service router).
- `GET /v1/reporting/incidents` via `reporting_incidents` (service router).
- `GET /v1/reporting/incidents/{incident_id}` via `reporting_incident_detail` (service router).
- `GET /v1/reporting/watch-targets` via `reporting_watch_targets` (service router).
- `GET /v1/reporting/review-queue` via `reporting_review_queue` (service router).
- `GET /v1/reporting/crm-targets` via `reporting_crm_targets` (service router).
- `GET /v1/reporting/meetings` via `reporting_meetings` (service router).
- `GET /v1/reporting/meetings/{meeting_id}` via `reporting_meeting_detail` (service router).
- `GET /v1/reporting/source-health` via `reporting_source_health` (service router).
- `GET /v1/reporting/kpis/catalog` via `reporting_kpi_catalog` (service router).
- `GET /v1/kpis/catalog` via `kpi_catalog` (service router).
- `GET /v1/intelligence/sources/health` via `source_health` (gateway).
- `GET /v1/reporting/events` via `reporting_events` (gateway).
- `GET /v1/reporting/events/{event_id}` via `reporting_event_detail` (gateway).
- `GET /v1/reporting/incidents` via `reporting_incidents` (gateway).
- `GET /v1/reporting/incidents/{incident_id}` via `reporting_incident_detail` (gateway).
- `GET /v1/reporting/watch-targets` via `reporting_watch_targets` (gateway).
- `GET /v1/reporting/review-queue` via `reporting_review_queue` (gateway).
- `GET /v1/reporting/crm-targets` via `reporting_crm_targets` (gateway).
- `GET /v1/reporting/meetings` via `reporting_meetings` (gateway).
- `GET /v1/reporting/meetings/{meeting_id}` via `reporting_meeting_detail` (gateway).
- `GET /v1/reporting/source-health` via `reporting_source_health` (gateway).
- `GET /v1/reporting/kpis/catalog` via `reporting_kpi_catalog` (gateway).
- `GET /v1/kpis/catalog` via `kpi_catalog` (gateway).

## Dependencies

- database read models.
- reporting operator headers.
- pagination cursors.

## Operations

- Treat idempotency headers as required where route handlers declare `Idempotency-Key`.
- Preserve policy, lineage, and audit fields when backfilling or replaying data.
- Use service-specific routes for isolated deployment and gateway routes for aggregate API access.
- Prefer fixtures and fake adapters in local development; live providers should be explicit environment configuration.
- Event projections expose exact address fields and latitude/longitude when geocoding is resolved; event format filters accept the same legacy aliases as the intelligence API.
- Incident projections expose primary affected company/domain and evidence URLs so console rows can render company/evidence inline without client-side reconstruction.

## Failure Modes

- Invalid or conflicting workflow requests are surfaced as `409` or validation errors by route handlers.
- Missing records are surfaced as `404` on detail/action endpoints.
- Provider outages should degrade or retry according to the service implementation rather than bypassing policy gates.
- Database or outbox failures leave the operation incomplete and should be retried with the same idempotency key when available.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=reporting-service uvicorn ghostrecon.service_apps.runtime:app --reload --port 8080
```

## Verification

```bash
pytest tests/unit/test_reporting_routes.py
```
