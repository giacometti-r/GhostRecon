# GhostRecon Sprint Tracker

## Current Stage

Stage: Sprint 7 scoring, corroboration, governance, and review workflows complete; Sprint 8 intelligence dashboard, review queue, and reporting is next.

The repository contains the production-oriented microservice scaffold, shared Python package, Docker/Compose setup, Helm chart, canonical persistence schema, source registry foundation, tests, and service documentation. Runtime implementation of the intelligence-first roadmap now includes shared source ingestion primitives, event-domain intelligence discovery, incident-news monitoring with watchlists, entity resolution, contact enrichment, persisted email candidates, verification payloads, versioned scoring, incident corroboration/rejection, suppression persistence, approval/rejection decisions, audit/outbox events, and inert CRM targets awaiting export.

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

### Sprint 6 - Entity Resolution, Company/Contact Enrichment, and Email Intelligence

- Added `EntityResolutionCase`, `ContactEnrichmentCandidate`, `OrganizationEmailPattern`, and `ReviewCandidate` persistence plus Alembic migration coverage.
- Extended contact and email-candidate records with origin, source-lineage, policy-snapshot, verification, review, idempotency, and optimistic-version fields.
- Implemented review-routed entity resolution across canonical accounts/domains, preserving alternatives for ambiguous or missing matches.
- Implemented fail-closed contact enrichment for missing lineage, prohibited participant reuse, breached-data provenance, and out-of-scope incident roles.
- Added stateful email-candidate persistence, organization email-pattern learning from verified candidates, verification-payload retention, and review routing for catch-all, ambiguous, and failed verification.
- Added `account.enriched`, `contact.discovered`, `email.candidate_generated`, `email.verified`, and `approval.requested` outbox emission for the Sprint 6 workflow boundary.
- Added enrichment, email, and read-only review APIs through the gateway and owning services, plus Celery task wrappers for entity resolution, contact enrichment, persisted email candidates, and verification batches.
- Aligned `ghostrecon.service_apps.runtime:app` with the service router factory so Docker, direct Uvicorn runs, and tests load the same service-specific routes.
- Added focused tests for source-lineage enforcement, participant reuse policy, incident role scope, breached-data rejection, verification mapping, model/migration surface, and new routes.

### Sprint 7 - Scoring, Corroboration, Governance, and Review Workflows

- Added `CandidateScore`, `ReviewDecision`, and `CrmTarget` persistence plus Alembic migration coverage for scoring components, review decisions, inert CRM targets, policy snapshot hashes, SLA metadata, suppression scope, and optimistic incident versions.
- Implemented versioned `sprint7.v1` fit, relevance, recency, confidence, and evidence scoring for event/incident/enrichment/email-derived candidates while keeping the legacy lead scoring API compatible.
- Added governance-owned approval, rejection, bulk-review, incident corroboration, incident false-positive rejection, suppression creation, suppression evaluation, and CRM-target read APIs through the gateway and owning services.
- Enforced fail-closed policy checks for source lineage, participant reuse, incident corroboration, suppression, retention, lawful basis, stale evidence, policy snapshot hashes, and optimistic versions before approval.
- Added `review.approved`, `review.rejected`, `crm_target.created`, and `suppression.created` events plus audit rows for governance decisions.
- Produced approved CRM targets as non-exported approval artifacts only; CRM export remains a separate Sprint 9 workflow and outreach remains a separate Sprint 10 workflow.
- Added focused tests for scoring configuration/routing, policy blockers, model/migration surface, event contracts, review decision routes, CRM-target routes, suppression routes, and incident governance routes.

## Baseline Acceptance Criteria

- `make test` passes in a fully provisioned Python environment.
- `docker compose up --build` starts the implemented local stack.
- `make helm-check` validates bundled and external datastore manifests.
- Every documented service has a local `README.md` and `TECHNICAL_README.md`.
- The runtime baseline remains provider-neutral above `CrmClient` and does not require a paid enrichment API.

## Future Sprints

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
