# reporting-service Technical README

## Responsibilities

- Define the KPI catalog and reporting response schemas.
- Serve Sprint 8 query-backed event, incident, watchlist, review, CRM-target, and source-health read models.
- Prepare for later materialized projections over versioned intelligence, review, governance, and CRM export events.
- Expose freshness/watermark metadata with every dashboard response.
- Support dashboards without locking data into one CRM or engagement provider.

## Interfaces

Implemented Sprint 8:

- `GET /v1/kpis/catalog`
- `GET /v1/reporting/kpis/catalog`
- `GET /v1/reporting/events`
- `GET /v1/reporting/events/{event_id}`
- `GET /v1/reporting/incidents`
- `GET /v1/reporting/incidents/{incident_id}`
- `GET /v1/reporting/watch-targets`
- `GET /v1/reporting/review-queue`
- `GET /v1/reporting/crm-targets`
- `GET /v1/reporting/source-health`

CRM export batches and reconciliation endpoints remain Sprint 9 work. All implemented collection endpoints use cursor pagination, explicit sorting, role-aware field projection, and filters from `docs/specifications/dashboard.md`.

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

- Sprint 8 read models query canonical tables directly and reference canonical GhostRecon IDs and source/evidence summaries, not copied unlicensed bodies.
- Materialized projections may replace query-backed reads later without changing the public reporting response metadata shape.
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

- KPI catalog, reporting route, metadata, and schema-version tests.
- Idempotent projection/rebuild and canonical-merge tests.
- Filter, pagination, role-field, and query performance tests.
- Watermark/stale/degraded-state tests under partial source failure.
- Canonical-to-projection reconciliation tests.

## Implemented Event Sources

Incident and watchlist projections consume implemented `news_article.ingested`, `security_incident.detected`, `security_incident.corroborated`, and `watch_target.created` outbox events when the projection runtime is added.

Sprint 7 review and CRM-target projections consume `lead.scored`, `approval.requested`, `review.approved`, `review.rejected`, `crm_target.created`, and `suppression.created` outbox events when the projection runtime is added.
