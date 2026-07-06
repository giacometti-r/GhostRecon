# console-service

## Purpose

`console-service` is the single internal UI boundary for intelligence dashboards, analyst review, approvals, watchlists, suppressions, replay, CRM export status, reconciliation, and health. The intelligence roadmap extends this service; it does not introduce another dashboard service.

The console renders reporting read models and invokes owning feature-service APIs for mutations. It does not own canonical intelligence, policy, scoring, or CRM export logic.

Sprint 8 implements backend reporting readiness only. A later UI sprint should implement the dashboard with Python Dash hosted from this service boundary, consuming reporting APIs for reads and gateway/owning service APIs for mutations.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=console-service`
- Current UI: minimal FastAPI HTML placeholder plus implemented review APIs.
- Future UI: Python Dash dashboard mounted within `console-service`; no Dash dependency is required until that sprint.

## Dashboard Sections

- Global event map, calendar, table, detail, and published participant roles.
- Global incident feed, evidence timeline, affected-company resolution, and watchlist state.
- Company/domain/incident/event-series/topic watchlists and follow-on coverage.
- Contact-enrichment and analyst-review queues with implemented approve/reject and bounded bulk-decision APIs.
- Typed inert CRM targets, future export batches, partial failures, and reconciliation.
- Source freshness and degraded-service indicators.

Detailed filters, actions, permissions, and acceptance criteria are in `docs/specifications/dashboard.md`.

## Dependencies

- Reporting service for dashboard projections, KPIs, and freshness metadata.
- Event/incident intelligence services for detail and watchlist mutations.
- Governance service for approvals, rejection, suppressions, retention, incident decisions, CRM targets, and policy decisions.
- CRM service for approved export batch actions and reconciliation.
- Gateway authentication/authorization and Redis/Celery operation state.

## Operations

- Restrict the console to authenticated internal operators.
- Enforce permissions server-side and audit every decision, policy change, replay, and export action.
- Display projection/source freshness independently from process health.
- Block unsafe mutations when policy/evidence is stale or a feature service is degraded.
- Sanitize all source-derived text and never render unlicensed full articles or prohibited personal data.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=console-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
