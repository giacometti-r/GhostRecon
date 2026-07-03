# reporting-service

## Purpose

`reporting-service` builds provider-neutral read models and KPI definitions for intelligence acquisition, source health, analyst review, CRM export, and downstream revenue workflows. It is the data backend for the existing `console-service` dashboard.

It does not own canonical intelligence, review decisions, CRM writes, or a separate UI.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=reporting-service`

## Read-Model Scope

- Event map/calendar/table and participant detail.
- Incident feed, evidence timelines, affected companies, and watchlist matches.
- Enrichment and analyst-review queues.
- Typed CRM targets, export batches, failures, and reconciliation.
- Source health, ingestion watermarks, service degradation, and projection freshness.

## Dependencies

- PostgreSQL canonical, event/outbox, review, audit, and export tables.
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
