# incident-intelligence-service Technical README

## Status

Sprint 5 incident-specific persistence, search/detail/watchlist interfaces, source parsing, Celery tasks, route registration, Helm registration, and focused tests are implemented.

## Responsibilities

Implemented foundation:

- Persist source `SourceDefinition` records and immutable `RawSourceItem` metadata, hashes, permitted excerpts, checkpoints, duplicate quarantine state, and source-health state.
- Execute shared HTTP page, RSS/Atom, scheduled-query, and GDELT DOC source adapters through source-registry fetches.
- Publish source-health responses and source-ingestion outbox events.

Implemented incident-domain work:

- Store canonical `NewsArticle` metadata with language, translation provenance, hashes, permitted excerpts, syndication cluster keys, and lineage.
- Deduplicate canonical URLs/content and group likely syndication families.
- Detect `SecurityIncident` candidates, affected-company alternatives, attack vectors, time windows, geography, confidence, and evidence.
- Apply deterministic authoritative and independent-source corroboration inputs; audited analyst decisions remain governance-owned.
- Create and manage `WatchTarget` records and attach follow-on coverage to canonical cases.
- Publish versioned discovery, corroboration, and watch-target contracts.

## Interfaces

- `GET /v1/intelligence/incidents`
- `GET /v1/intelligence/incidents/{incident_id}`
- `POST /v1/intelligence/watch-targets`
- `GET /v1/intelligence/watch-targets`
- `PATCH /v1/intelligence/watch-targets/{watch_target_id}`
- `POST /v1/intelligence/incidents/{incident_id}/promote-to-watchlist`
- `GET /v1/intelligence/sources/health?kind=incident`

Mutations require actor context, `Idempotency-Key`, and optimistic version where applicable.

## Events

Implemented source-ingestion events:

- `source.fetch_succeeded`
- `source.fetch_failed`
- `source.item_ingested`

Implemented incident-domain events:

- `news_article.ingested`
- `security_incident.detected`
- `security_incident.corroborated`
- `watch_target.created`

Contracts use the envelope and payload rules in `docs/specifications/intelligence-pipeline.md`.

## Corroboration Rules

- New cases have status `candidate`.
- An authoritative disclosure is explicit and tied to the case by the affected organization or competent authority.
- Independent-source corroboration excludes syndicated copies, copied releases, and common upstream reporting.
- Analyst decisions reference actor, reason, evidence snapshot, and policy version and are owned by governance.
- Watchlist promotion is orthogonal to corroboration and retains `origin_incident_id`.

## Data Rules

- Article identity prefers canonical URL and content hash; fuzzy syndication clustering does not erase article lineage.
- Incident identity uses affected company, observed window, attack vector, and evidence overlap with review for ambiguous matches.
- Translated fields retain original language/text metadata and translation provider/version.
- API/events carry only permitted excerpts, never unlicensed bodies.
- No breached personal data enters raw metadata, canonical records, logs, or model prompts.

## Failure Modes

- Discovery provider outage: continue independent sources and expose partial/stale coverage.
- Rate limit: checkpoint and retry after provider guidance with jitter.
- Translation unavailable: retain original-language record and mark translation state.
- Company ambiguity: preserve alternatives and block contact/CRM eligibility.
- False-positive cluster: reject with audit in governance; do not delete evidence.
- Watch query drift: pause noisy target, preserve existing matches, and require reviewed query change.

## Testing

Sprint 5 tests cover:

- GDELT JSON parsing and RSS/advisory article extraction.
- Canonical article metadata, no-body storage, language metadata, and dedupe keys.
- Incident candidate extraction, affected-company/attack-vector metadata, and source-lineage event contracts.
- Incident read routes and idempotent promotion route behavior.
- Helm service registration through the chart validation gate.
