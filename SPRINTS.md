# GhostRecon Sprint Tracker

## Current Stage

Stage: Sprint 5 global incident-news monitoring and watchlists complete; Sprint 6 entity resolution, company/contact enrichment, and email intelligence is next.

The repository contains the production-oriented microservice scaffold, shared Python package, Docker/Compose setup, Helm chart, canonical persistence schema, source registry foundation, tests, and service documentation. Runtime implementation of the intelligence-first roadmap now includes shared source ingestion primitives, event-domain intelligence discovery, and incident-news monitoring with watchlists.

## Done

### Sprint 0 - Planning and Architecture

- Read `deep-research-report.md`, which remains historical research.
- Converted the n8n orchestration model into a Python microservice architecture.
- Selected Attio as the first CRM while preserving a provider-neutral adapter boundary.
- Selected PostgreSQL and Redis as the event/state backbone for v1.
- Selected Scrapy for public company-page crawling and `umuterturk/email-verifier` for email validation.
- Defined production-grade operator and technical documentation requirements for each microservice.

### Sprint 1 - Foundation Scaffold

- Added the Python package scaffold under `src/ghostrecon`.
- Added canonical API schemas, database models, and the initial Alembic migration.
- Added shared FastAPI and Celery runtime entrypoints.
- Added deterministic business logic for scoring, suppression, email candidates, sequence eligibility, prep packets, enrichment, and Attio webhook signature verification.
- Added Dockerfile, Docker Compose, Helm chart, Kubernetes examples, Makefile, CI workflow, and smoke-import script.
- Added unit tests for deterministic service logic.
- Added SOPS + Age-ready Helm secret scaffolding with placeholders.
- Added persistent PostgreSQL and Redis Helm subcharts, generated datastore URLs, authenticated Redis access, least-privilege PostgreSQL initialization, migration hooks, and internal/external render validation.

### Sprint 2 - Persistence Baseline

- Added canonical PostgreSQL models and migration coverage for accounts, contacts, leads, signals, email candidates, suppressions, audit events, and transactional outbox events.
- Added stable identifiers, source-lineage fields, idempotency keys, and CRM-reference fields to the baseline schema.
- Preserved database-backed suppression, repository, dead-letter, and replay expansion as implementation work that intelligence services will consume rather than redesign.
- Established PostgreSQL as the canonical data/audit store and Redis as queue, lock, and rate-limit coordination.

### Sprint 3 - Intelligence Ingestion Foundation and Source Registry

- Added `SourceDefinition` and `RawSourceItem` PostgreSQL models plus Alembic migration coverage for source policy, participant reuse state, content storage policy, freshness/checkpoint state, raw metadata, permitted excerpts, hashes, parse status, duplicate quarantine, and idempotency keys.
- Added shared adapters and fixture-testable parsers for HTTP pages, Schema.org JSON-LD events, ICS calendars, RSS/Atom feeds, and scheduled provider query sources.
- Added deterministic normalization helpers for canonical URLs, tracking-parameter removal, content hashing, raw-item idempotency, permitted-excerpt bounding, and body-field exclusion from raw metadata.
- Added source-health models and `GET /v1/intelligence/sources/health`, exposing freshness, policy, enabled/degraded state, checkpoints, failures, and last-error metadata.
- Extended event envelopes with schema version, producer, correlation ID, source definition ID, and source item IDs; added `source.fetch_succeeded`, `source.fetch_failed`, and `source.item_ingested` events.
- Added the `ghostrecon.fetch_source` Celery task to fetch one registered source, persist raw items idempotently, update checkpoints/freshness, and enqueue outbox events.

### Sprint 4 - Global Cybersecurity Event and Participant Discovery

- Added `CyberEvent` and `EventParticipant` PostgreSQL models plus Alembic migration coverage for event/source lineage, original and normalized time fields, IANA timezone state, format, venue/geography, topics, organizers, canonical state, dedupe keys, participant reuse state, and eligibility flags.
- Seeded official event source definitions for DEF CON, Black Hat, BSides, OWASP, and FIRST with conservative `unknown` participant reuse until governance records explicit reuse evidence.
- Added event parsing and normalization for existing Schema.org, ICS, RSS/Atom, and HTTP-page raw-item metadata, including deterministic event/participant dedupe keys and fail-closed participant eligibility.
- Added `cyber_event.discovered` and `event_participant.discovered` outbox events with source-definition and raw-item lineage.
- Added `ghostrecon.fetch_event_source` and `ghostrecon.parse_pending_event_items` Celery tasks.
- Added event intelligence read APIs for event list/detail, event participants, and global participant search, exposed through `event-intelligence-service` and the gateway scaffold.
- Added Helm service registration and focused tests for timezone handling, parser extraction, participant reuse policy, event contracts, and API responses.

### Sprint 5 - Global Incident-News Monitoring and Watchlists

- Implemented `incident-intelligence-service`, `NewsArticle`, `SecurityIncident`, `SecurityIncidentEvidence`, and `WatchTarget` persistence.
- Added GDELT DOC discovery, trusted RSS/Atom and advisory source support, seeded conservative incident sources, and retained article metadata/permitted excerpts without storing unlicensed full articles.
- Added deterministic article normalization, canonical URL/content/syndication dedupe, affected-company/attack-vector/geography/language metadata, and source/evidence lineage.
- Added `news_article.ingested`, `security_incident.detected`, `security_incident.corroborated`, and `watch_target.created` outbox events.
- Added `ghostrecon.fetch_incident_source` and `ghostrecon.parse_pending_incident_items` Celery tasks.
- Added incident read APIs, watch-target create/list/patch APIs, and idempotent incident promotion to watchlists, exposed through `incident-intelligence-service` and the gateway scaffold.
- Added Helm service registration and focused tests for GDELT parsing, incident candidate extraction, event contracts, route responses, metadata-only storage, and watchlist promotion.

## Baseline Acceptance Criteria

- `make test` passes in a fully provisioned Python environment.
- `docker compose up --build` starts the implemented local stack.
- `make helm-check` validates bundled and external datastore manifests.
- Every documented service has a local `README.md` and `TECHNICAL_README.md`.
- The runtime baseline remains provider-neutral above `CrmClient` and does not require a paid enrichment API.

## Future Sprints

### Sprint 6 - Entity Resolution, Company/Contact Enrichment, and Email Intelligence

- Resolve organizations and domains across events, incidents, existing canonical accounts, and CRM references.
- Enrich eligible public business contacts in security, IT, risk, and communications roles.
- Learn organization-specific email patterns, persist candidates and verification payloads, and batch verification through the sidecar.
- Extend lead-source taxonomy with `cyber_event` and `security_incident`.

Acceptance: source permission and lineage follow every contact; breached personal data is rejected; ambiguous resolution or email verification routes to review.

### Sprint 7 - Scoring, Corroboration, Governance, and Review Workflows

- Version fit, relevance, recency, confidence, and evidence scoring configuration.
- Enforce incident corroboration, participant-reuse policy, suppression, retention, and lawful-basis rules.
- Add approval/rejection APIs, reason codes, bulk-review safeguards, SLA timers, and complete audit trails.
- Produce typed review candidates and CRM targets without initiating outreach.

Acceptance: false-positive rejection, analyst override, suppression, retention, approval auditing, and policy fail-closed behavior pass integration tests.

### Sprint 8 - Intelligence Dashboard, Review Queue, and Reporting

- Build the dashboard in the existing FastAPI/Jinja `console-service`; do not create another dashboard service.
- Back dashboard views with `reporting-service` read models and freshness metadata.
- Implement event map/calendar/table, participant details, incident feed, watchlists, enrichment/review queues, export batches, reconciliation failures, and source health.
- Add role-based view/action permissions and auditable bulk review.

Acceptance: dashboard filters/actions meet `docs/specifications/dashboard.md`; stale and degraded services are visible; bulk decisions remain idempotent and auditable.

### Sprint 9 - Attio Production Integration and Provider-Neutral CRM Export

- Implement review-gated, idempotent `CrmExportBatch` and `CrmExportItem` workflows behind `CrmClient`.
- Map custom Attio `cyber_events` and `security_incidents` objects plus standard People and Companies.
- Configure separate typed lists for events, event participants, incidents, companies, and incident contacts.
- Upsert People and Companies by stable identifiers before list insertion; preserve GhostRecon IDs and source lineage.
- Add rate-limit queues, partial-failure recovery, reconciliation jobs, and mocked contract tests.

Acceptance: only approved targets export; retries do not duplicate records or list entries; partial failures reconcile; exports never auto-enroll outreach.

### Sprint 10 - Sequencing

- Implement SMTP sending, IMAP reply detection, bounce processing, and unsubscribe ingestion.
- Add per-domain and per-owner rate limits, templates, step scheduling, pause/resume, and independent approval gates.
- Re-evaluate suppression and lawful basis immediately before every outbound action.

### Sprint 11 - Meeting Handoff

- Add a calendar integration adapter.
- Generate AE/SE prep packets from canonical event, incident, account, and contact state.
- Sync approved meeting outcomes and follow-up tasks through `CrmClient`.

### Sprint 12 - Hardening and Pilot

- Add load tests, backup/restore drills, SLO alerts, stale-source alerts, runbooks, PodDisruptionBudgets, and external-secret templates.
- Exercise source outages, rate limits, partial CRM failures, reconciliation, replay, retention, and disaster recovery.
- Run a pilot with one territory or segment and document production-readiness signoff.
