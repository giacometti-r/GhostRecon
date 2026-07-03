# event-intelligence-service

## Status

The shared Sprint 3 source registry and raw-item foundation is implemented. Sprint 4 adds event-domain runtime, `CyberEvent` / `EventParticipant` persistence, Celery parsing tasks, read APIs, and Helm deployment registration.

## Purpose

`event-intelligence-service` discovers global cybersecurity events and explicitly reusable published participants. It registers event sources, fetches official content, normalizes event/time/location/series data, deduplicates records, preserves lineage, and publishes canonical discovery events.

It does not enrich contacts, decide CRM approval, write to a CRM, or enroll outreach.

## Sources

- Official conference and organizer pages.
- Schema.org `Event` data.
- ICS calendars.
- RSS/Atom feeds.
- Approved provider APIs.

Initial series configuration should cover DEF CON, Black Hat, BSides, OWASP, and FIRST. Each concrete source has independent terms, rate limits, and participant-reuse policy.

## Dependencies

- PostgreSQL for source registry, raw items, canonical events, participants, and lineage.
- Redis/Celery for scheduled fetch, parse, normalization, and replay jobs.
- Governance service for source-policy decisions.
- Reporting service for event and source-health projections.

## Operator Rules

- Treat `unknown` participant reuse the same as `prohibited` for contact extraction and CRM export.
- Store metadata and permitted excerpts only.
- Retain original date/time/timezone and normalize to UTC plus IANA timezone.
- Do not bypass authentication, CAPTCHAs, robots policy, paywalls, or rate limits.
- Pause a source on repeated selector/schema failure rather than emitting low-confidence records silently.

## Health and Metrics

`GET /v1/intelligence/sources/health?kind=event` exposes registered event-source freshness, policy state, checkpoints, failures, and last-error metadata through the shared source registry. Also monitor parse yield, event/participant discovery rate, dedupe rate, ambiguous timezone count, and downstream projection lag.

Recovery procedures are in `docs/runbooks/operations.md`.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=event-intelligence-service \
uvicorn ghostrecon.service_apps.runtime:app --reload
```

## Related Specifications

- `docs/specifications/intelligence-pipeline.md`
- `docs/specifications/dashboard.md`
- `services/event-intelligence-service/TECHNICAL_README.md`
