# event-intelligence-service Technical README

## Status

Sprint 3 source registry interfaces are implemented. Sprint 4 adds event-specific search/detail interfaces, `CyberEvent` / `EventParticipant` persistence, event-domain parsing, and event discovery outbox contracts.

## Responsibilities

Implemented foundation:

- Persist source `SourceDefinition` records and immutable `RawSourceItem` metadata, hashes, permitted excerpts, checkpoints, duplicate quarantine state, and source-health state.
- Execute shared HTTP page, Schema.org, ICS, RSS/Atom, and scheduled-query source adapters through `ghostrecon.fetch_source`.
- Publish source-health responses and source-ingestion outbox events.

Implemented event-domain work:

- Parse and normalize `CyberEvent` and `EventParticipant` records.
- Resolve series, UTC/IANA time, geography, format, topic, organizer, and source lineage.
- Deduplicate exact and deterministic event/participant candidates without losing evidence.
- Enforce participant-reuse state before publishing downstream eligibility.
- Publish source health and versioned discovery contracts.

## Interfaces

- `GET /v1/intelligence/events`
- `GET /v1/intelligence/events/{event_id}`
- `GET /v1/intelligence/events/{event_id}/participants`
- `GET /v1/intelligence/participants`
- `GET /v1/intelligence/sources/health?kind=event` - implemented for registered source definitions

Source configuration/replay endpoints are administrator-only and require audit/idempotency controls.

## Events

Implemented source-ingestion events:

- `source.fetch_succeeded`
- `source.fetch_failed`
- `source.item_ingested`

Implemented event-domain events:

- `cyber_event.discovered`
- `event_participant.discovered`

Contracts use the envelope and payload rules in `docs/specifications/intelligence-pipeline.md`.

## Data Rules

- Raw-item identity prefers source external ID, then canonical URL plus content hash.
- Event identity prefers official external ID, then event series/start/organizer; fuzzy matches require confidence and review.
- Preserve original timestamp/timezone and parsed timezone confidence.
- Participant records contain only published identity, organization, role/type, profile URL, permission evidence, and resolution metadata.
- `contact_extraction_allowed` and `crm_export_allowed` are false unless reuse is explicitly `allowed` for that scope.
- Never publish unlicensed full text in API or event payloads.

## Failure Modes

- Source unavailable/rate limited: keep the checkpoint, back off, and expose degraded freshness.
- HTML/schema change: quarantine parse results, alert on yield collapse, and avoid mass deletions.
- Ambiguous local time: keep source value, mark unresolved, and route to review.
- Duplicate ambiguity: retain both canonical candidates until audited merge.
- Source policy expires/changes: invalidate downstream contact/export eligibility.

## Testing

Implemented foundation tests cover:

- Schema.org, ICS, RSS/Atom, and HTML adapter fixtures.
- Source lineage, permitted excerpts, idempotency, freshness states, and source-ingestion event contracts.

Sprint 4 tests cover:

- Exact and deterministic event and participant dedupe.
- DST, timezone, all-day, virtual, and multilingual metadata.
- Explicit `allowed` versus `unknown`/`prohibited` participant-reuse policy.
- Parser degradation, ambiguous time, source-policy change, and downstream eligibility invalidation.
