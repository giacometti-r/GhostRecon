# reporting-service Technical README

## Responsibilities

- Define the KPI catalog and projection schemas.
- Consume versioned intelligence, review, governance, and CRM export events.
- Materialize event, incident, watchlist, queue, export, reconciliation, and source-health views.
- Expose freshness/watermark metadata with every dashboard response.
- Support dashboards without locking data into one CRM or engagement provider.

## Interfaces

Implemented baseline:

- `GET /v1/kpis/catalog`

Target reporting interfaces:

- `GET /v1/reporting/events`
- `GET /v1/reporting/events/{event_id}`
- `GET /v1/reporting/incidents`
- `GET /v1/reporting/incidents/{incident_id}`
- `GET /v1/reporting/watch-targets`
- `GET /v1/reporting/review-queue`
- `GET /v1/reporting/crm-exports`
- `GET /v1/reporting/source-health`

All collection endpoints use cursor pagination, explicit sorting, role-aware field projection, and filters from `docs/specifications/dashboard.md`.

## KPI Families

- Global event/incident coverage by geography, language, source, topic, and time.
- Source freshness, fetch success, parse yield, duplicate rate, and projection lag.
- Participant reuse eligibility and policy-block counts.
- Incident candidate/corroboration time/method, false positives, and watchlist follow-on coverage.
- Entity/contact resolution yield and correction rate.
- Review age/SLA, approval/rejection, conflict, and policy-block rate.
- CRM batch latency, item outcomes, retries, rate limits, and reconciliation age.
- Sequence, pipeline, meeting, and pre-sales outcomes after approved activation.

## Projection Rules

- Projections reference canonical GhostRecon IDs and source/evidence summaries, not copied unlicensed bodies.
- Merges/tombstones redirect to the surviving canonical record and remain auditable.
- Reprocessing an event is idempotent by event ID/schema version.
- A read response includes `generated_at`, watermarks, projection version, `stale`, and degraded dependencies.

## Failure Modes

- Event/outbox lag: expose a stale marker and current watermark.
- Projection poison message: quarantine with event/audit context and continue independent partitions where safe.
- Query overload: pre-aggregate and cache while preserving freshness metadata.
- Missing/incompatible event fields: reject incompatible versions and alert.
- Count drift: stop declaring the projection current until reconciliation/rebuild succeeds.

## Testing

- KPI catalog and schema-version tests.
- Idempotent projection/rebuild and canonical-merge tests.
- Filter, pagination, role-field, and query performance tests.
- Watermark/stale/degraded-state tests under partial source failure.
- Canonical-to-projection reconciliation tests.

## Sprint 5 Sources

Incident and watchlist projections consume implemented `news_article.ingested`, `security_incident.detected`, `security_incident.corroborated`, and `watch_target.created` outbox events when the projection runtime is added.
