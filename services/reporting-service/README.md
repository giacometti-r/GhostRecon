# reporting-service

## Purpose

`reporting-service` builds provider-neutral read models and KPI definitions for intelligence acquisition, source health, analyst review, CRM export, sequencing, meeting handoff, and downstream revenue workflows. It is the data backend for the existing `console-service` dashboard.

It does not own canonical intelligence, review decisions, CRM writes, or a separate UI.

Sprint 8 uses query-backed read models over canonical tables and service-owned serializers. Materialized projection tables can be added later when latency, replay, or scale requires them.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=reporting-service`

## Read-Model Scope

- Event map/calendar/table and participant detail.
- Incident feed, evidence timelines, affected companies, and watchlist matches.
- Enrichment and analyst-review queues.
- Typed CRM targets, future export batches, failures, and reconciliation.
- Meeting handoff, prep-packet, outcome, follow-up task, Google Calendar, and CRM sync state.
- Source health, ingestion watermarks, service degradation, and projection freshness.

Implemented Sprint 8 APIs:

- `GET /v1/reporting/events`
- `GET /v1/reporting/events/{event_id}`
- `GET /v1/reporting/incidents`
- `GET /v1/reporting/incidents/{incident_id}`
- `GET /v1/reporting/watch-targets`
- `GET /v1/reporting/review-queue`
- `GET /v1/reporting/crm-targets`
- `GET /v1/reporting/meetings`
- `GET /v1/reporting/meetings/{meeting_id}`
- `GET /v1/reporting/source-health`
- `GET /v1/reporting/kpis/catalog`
- `GET /v1/kpis/catalog`

Every reporting response includes `generated_at`, watermarks, projection version, stale state, and degraded dependency names.

## Dependencies

- PostgreSQL canonical, event/outbox, score, review, CRM-target, audit, and future export tables.
- Event/incident intelligence source checkpoints and lineage.
- Prometheus for service/process metrics.
- Optional future warehouse/BI exports.

## Operations

- Keep operational, intelligence-quality, review, export, and revenue KPIs distinct.
- Every read response exposes generation time, source watermark, projection version, and stale/degraded state.
- Monitor outbox lag, projection lag/failures, query latency, and count drift against canonical tables.
- Rebuild affected projections rather than hiding staleness with cache extension.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=reporting-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
