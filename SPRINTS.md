# GhostRecon Sprint Tracker

## Current Stage

Stage: Sprint 22 meeting detail readability complete; Sprint 23 end-to-end live demo runbook is next. The local Compose stack now has repeatable reset, migration, linked deterministic fake data, dashboard workflow coverage, watchlist monitoring scheduling, sequence definition/import workflows, and health-check commands for validating a ready local demo without manual database commands.

The repository contains the production-oriented microservice scaffold, shared Python package, Docker/Compose setup, Helm chart, canonical persistence schema, source registry foundation, tests, and service documentation. Runtime implementation of the intelligence-first roadmap now includes shared source ingestion primitives, event-domain intelligence discovery, incident-news monitoring with watchlists, entity resolution, contact enrichment, persisted email candidates, verification payloads, versioned scoring, incident corroboration/rejection, suppression persistence, approval/rejection decisions, audit/outbox events, CRM export batches/items, reporting-service dashboard read APIs with freshness/degraded metadata, the first persisted sequencing runtime for separately approved outreach, persisted Google Calendar meeting handoff with prep packets, outcomes, follow-up tasks, CRM sync state, meeting reporting read APIs, and the first Python Dash operator dashboard mounted in `console-service`.

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
- Added deterministic business logic for scoring, suppression, email candidates, sequence eligibility, prep packets, enrichment, and CRM service workflows.
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
- Added stateful email-candidate persistence, organization email-pattern learning from verified candidates, verification-payload retention, and review routing for catch-all, ambiguous, and failed verification. Generated candidates are unscored permutations validated through the verifier workflow.
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

### Sprint 8 - Backend Reporting and Dashboard Readiness

- Fixed the Sprint 7 type gate by making defaulted scoring numeric coercion non-optional without changing scoring outputs.
- Added metadata-wrapped reporting contracts for events, event detail, incidents, incident detail, watch targets, review queues, CRM targets, source health, and KPI catalog.
- Implemented query-backed reporting read models over canonical tables and existing service-owned converters; materialized projections remain a later scaling option.
- Added cursor pagination, stable sorting, dashboard filters, projection version, generated-at timestamps, source watermarks, stale flags, and degraded dependency names on reporting responses.
- Added operator role context through `X-Operator-Role` and viewer-level redaction for review, CRM-target, and source-health policy details.
- Kept dashboard UI implementation deferred; documented Python Dash as the future console UI direction without adding Dash dependencies.
- Added focused reporting tests for route contracts, metadata/freshness, cursor behavior, role projection, KPI catalog, and scoring numeric-coercion regression.

### Sprint 9 - Attio Production Integration and Provider-Neutral CRM Export

- Added review-gated, idempotent `CrmExportBatch` and `CrmExportItem` workflows behind the provider-neutral `CrmClient` boundary.
- Added Attio object/list mapping for custom cyber events/security incidents and standard People/Companies, preserving GhostRecon IDs and source lineage.
- Added CRM export start/detail/retry APIs through the gateway and `crm-service`, plus lifecycle outbox events for batch and item state.
- Added stable identifier upserts, list insertion, retryable rate-limit handling, partial-failure state, and export status updates without sequencing side effects.
- Added mocked Attio and route tests for export contracts, target eligibility, idempotent selection hashing, and provider rate-limit behavior.

### Sprint 10 - Sequencing and Outreach Runtime

- Added persisted `Sequence`, `SequenceStep`, `SequenceEnrollment`, `OutboundEmail`, `InboundEmailEvent`, and `SequenceSuppressionEvent` tables plus migration coverage.
- Added sequence template, enrollment, list/detail, pause/resume/cancel, unsubscribe, and existing eligibility APIs through the gateway and `sequencing-service`.
- Implemented separate outreach approval for enrollment; exported CRM targets do not imply outreach approval and CRM export never invokes sequencing.
- Added stdlib-backed SMTP/IMAP adapter boundaries, Celery tasks for due-step processing and inbound polling, retry/backoff state, and per-domain/sender/channel rate-limit checks.
- Re-evaluated verified email, lawful basis, do-not-contact, suppression, and current contact evidence before each send; suppression failures pause/suppress enrollment and preserve audit/outbox evidence.
- Added lifecycle events for `sequence.enrolled`, `sequence.paused`, `sequence.completed`, `email.sent`, `reply.received`, `bounce.received`, and `unsubscribe.received`.
- Added focused tests for sequence route contracts, model registration, policy gates, rate-limit blocking, inbound polling with fakes, worker registration, and event contracts.

### Sprint 11 - Google Calendar Meeting Handoff

- Added persisted `MeetingHandoff`, `MeetingPrepPacket`, and `MeetingFollowUpTask` tables plus migration coverage.
- Added Google Calendar event create/cancel and free-busy support behind a fakeable calendar adapter, with service-account configuration for production.
- Added meeting create/list/detail, prep-packet generation, outcome recording, cancel, CRM retry, and calendar availability APIs through the gateway and `meeting-handoff-service`.
- Required exported/current CRM targets before meeting handoff and checked email suppressions before sending calendar invites.
- Completed linked active sequence enrollments with `meeting_booked` state when a meeting is scheduled.
- Generated AE/SE prep packets from canonical account, contact, signal, event, and incident state while keeping the old stateless helper compatible.
- Synced meeting outcomes and follow-up tasks through provider-neutral `CrmClient` plans and recorded retryable/terminal CRM sync state.
- Added `meeting.booked`, `meeting.prep_packet_generated`, `meeting.outcome_recorded`, `meeting.follow_up_task_created`, and `crm.synced` event coverage.
- Added reporting-service meeting list/detail read APIs and meeting KPI catalog entries.
- Updated service, architecture, operations, dashboard, Helm, and source-policy documentation for Google Calendar meeting handoff.

### Sprint 12 - Python Dash Intelligence Dashboard UI

- Added Python Dash, Plotly, and Lucide-compatible icon support inside the existing `console-service`; no independent dashboard service, datastore, or canonical-table access was introduced.
- Mounted the Dash app at the console root while preserving FastAPI system routes and existing `/v1/review/*` APIs.
- Added a gateway-backed console API client that propagates actor, role, timeout, authorization, idempotency, stale, and degraded-state context.
- Implemented dashboard routes for overview, events, event detail, incidents, incident detail, watchlists, review/enrichment queues, CRM targets/export batches, sequence state, meetings, meeting detail, and source health.
- Added reporting-backed freshness/degraded banners, cursor-aware tables, linkable filter state, map/calendar table fallbacks, and role-aware action controls.
- Wired existing owner-service mutations for review decisions, bounded bulk review, incident watch promotion, watch target toggle, CRM export/retry, sequence pause/resume/cancel, and meeting prep/outcome/cancel/CRM retry.
- Kept source-health operations read-only until owning source-operations APIs exist in hardening/pilot work.
- Added local Compose support for `console-service` on `GHOSTRECON_CONSOLE_HTTP_PORT`, plus Helm defaults for the internal gateway URL.
- Updated dashboard, service, architecture, operations, Helm, README, and sprint documentation for the implemented Dash console.

### Sprint 13 - Compose Migration Bootstrap

- Added a one-shot local Compose `migrate` service that runs `alembic upgrade head` against the Compose Postgres database before API and worker services start.
- Made `gateway-service`, `console-service`, and the Celery worker depend on successful Compose migration completion.
- Added schema-aware `/readyz` checks for gateway, reporting, and console services while keeping `/healthz` process-only.
- Added clear readiness failures for unreachable databases, missing `alembic_version`, and missing public tables instead of surfacing `UndefinedTableError` through reporting APIs.
- Added a minimal schema-only `scripts/demo_reset.sh` and `make demo-reset-schema` path for resetting local Compose volumes and reapplying migrations.
- Updated local development documentation for automatic Compose migrations and direct non-Compose migration usage.

### Sprint 14 - Local Demo Reset and Health Scripts

- Added deterministic local smoke seeding through `python -m ghostrecon.demo_seed`, guarded against non-local environments unless explicitly overridden.
- Expanded `scripts/demo_reset.sh` to reset Compose volumes, start Postgres/Redis, apply migrations, and seed local demo rows.
- Added `scripts/demo_check.sh` to verify required containers, representative PostgreSQL schema and seed rows, Redis, gateway health/readiness/reporting APIs, console health/readiness/root, and Dash callback dependency metadata.
- Added `make demo-reset`, `make demo-check`, and `make demo` while preserving `make demo-reset-schema` compatibility.
- Updated local development documentation for the repeatable demo command sequence.

### Sprint 15 - Deterministic Fake Demo Data

- Expanded local-only deterministic seeding to cover linked events, event participants, incidents, watch targets, review candidates, CRM targets, CRM export batches/items, accounts, contacts, sequences, meetings, prep packets, follow-up tasks, and fresh/degraded source-health records.
- Seeded actionable local demo records for review approve/reject, incident watch promotion, watch target toggle, CRM export start/retry, sequence pause/resume/cancel, meeting prep generation, meeting outcome recording, and meeting CRM retry.
- Linked fixture records so dashboard list pages, detail pages, and owner-service action APIs have realistic targets after `make demo-reset`.
- Expanded `demo_check.sh` to verify the broader seeded schema plus meeting detail, sequence enrollment, and CRM export batch detail endpoints.

### Sprint 16 - Dashboard Navigation and Interactivity Fixes

- Fixed Dash dashboard navigation by making sidebar, detail, and pagination links use client-side `dcc.Location` routing consistently.
- Added active sidebar navigation state, including parent-route highlighting for detail pages and `aria-current` for the current section.
- Improved route-level API failure rendering so failed gateway/reporting reads show endpoint and status details while preserving any available page content.
- Added Playwright browser acceptance coverage for sidebar tab clicks, URL/content changes, refresh, filters, pagination, role switching, detail links, action buttons, and visible failed-API states.
- Kept console reads and writes inside the existing gateway-backed `console-service` boundary with no direct canonical table access.

### Sprint 17 - Global Events Dashboard Workflow

- Added event address/geocoding fields, canonical event formats `in-person`, `online`, `hybrid`, and `unknown`, and legacy `physical`/`virtual` alias support.
- Added Nominatim-compatible and deterministic local-demo geocoder adapters, non-blocking geocode failure handling, and map-ready event reporting fields.
- Added manual event creation and optimistic-version event edit APIs behind the existing event-intelligence boundary.
- Updated the Dash events workflow with a larger coordinate-backed event map, create/edit modals, bullet-free event detail topics, governance-reviewer-only metadata, and durable participant enrichment-queue button disabling.
- Seeded local demo event coordinates and added focused tests for event aliases, geocoder behavior, event create/update routes, reporting projection fields, and console role rendering.

### Sprint 18 - Global Incidents Governance and Watchlist Promotion

- Added incident grouping, primary company/domain context, and evidence URL persistence for company-specific incident rows.
- Updated incident ingestion and manual creation to split multi-company contexts into separate canonical incident rows with a shared `incident_group_key`.
- Made incident watch promotion optimistic-version aware, corroborated-only, company-targeted, actor-owned, and idempotent at the company watch-target key.
- Added incident revert governance flow to move corroborated incidents back to candidate state with audit/review-decision evidence.
- Updated the Dash incidents workflow with inline company/evidence rendering, hidden confidence/languages, table-only open links, Revert after corroboration, local dismissed rows after reject/promote, governance-reviewer-only metadata, and a manual incident modal.
- Seeded a multi-company local demo incident group and added focused tests for incident splitting, route contracts, revert routing, company watch promotion, schema registration, and console action payloads.

### Sprint 19 - Watchlist Detail, Ownership, Contact Discovery, and Monitoring

- Made the Watchlist dashboard company-centric with owner, monitoring state, Open actions, and a `Watchlist Item` detail page.
- Added role-aware watch target reporting/detail projections that hide origin incidents except for governance reviewers.
- Preserved incident-promotion ownership from the approving actor and kept monitoring toggles optimistic-version aware through the existing watch target patch contract.
- Added adapter-backed OpenSERP contact discovery with the required LinkedIn CISO/CTO/security-leader Google dork, persisted search lineage as source/raw-item evidence, and exposed `Find Contact` through the dashboard.
- Added durable watchlist monitoring state and run history plus hourly Celery beat scheduling for local Compose and Helm worker/scheduler deployments.
- Added fake local demo providers and focused tests for watchlist routes, console actions, role projection, query generation, and monitoring contract surfaces.

### Sprint 20 - Analyst Review Demo Data and Domain Discovery

- Expanded deterministic local demo seed data with realistic linked entity-resolution cases, contact enrichment candidates, email candidates, watch monitoring runs, and review candidates.
- Added OpenSERP-backed official website discovery for contact enrichment candidates and normalized selected websites to registrable domains with public-suffix-aware parsing.
- Routed failed, ambiguous, or suspicious domain discovery into analyst review instead of silently confirming a match.
- Added `Discover Domain` actions to the contact enrichment queue while keeping all mutations routed through gateway/owning-service APIs.
- Updated local demo checks to verify scheduler, monitoring, domain discovery, contact enrichment, and email candidate seed rows.
- Added focused tests for domain normalization, provider query construction, route contracts, dashboard rendering, and governance-only watchlist metadata.

### Sprint 21 - Sequence Definitions, Multi-Channel Steps, and CRM Imports

- Added versioned sequence definitions with multi-channel email, call, and Google Meet steps plus optimistic definition-version updates.
- Added persisted sequence step activities so email approvals, call tasks, and Google Meet scheduling are represented without forcing non-email work through outbound email rows.
- Changed due email steps to create pending approval activities and `pending_approval` outbound emails; authorized approval performs the final policy checks before sending.
- Added provider-neutral CRM prospect search/import through the CRM adapter, with Attio record search support and deterministic local fake prospects when no Attio token is configured.
- Added sequencing APIs for CRM prospect import, activity listing, email approval, activity completion, and meeting scheduling while preserving separate outreach approval.
- Updated the Dash Sequence State workflow with a Sequence Definitions path, create/edit controls, CRM prospect import, and activity actions.

### Sprint 22 - Meeting Detail Readability and Prep Packet Legibility

- Replaced raw nested prep-packet rendering in Meeting Detail with structured account context, contacts, signals, talk tracks, risks/incidents, and source-context sections.
- Rendered list-like prep packet values as clean rows/chips instead of bullet artifacts or JSON-like formatting noise.
- Added prep packet spacing and wrapping styles while preserving existing meeting handoff, prep generation, outcome, cancel, and CRM retry actions.
- Added focused console coverage for sequence workflow rendering and structured meeting prep packet rendering.

## Baseline Acceptance Criteria

- `make test` passes in a fully provisioned Python environment.
- `docker compose up --build` starts the implemented local stack.
- `make helm-check` validates bundled and external datastore manifests.
- Every documented service has a local `README.md` and `TECHNICAL_README.md`.
- The runtime baseline remains provider-neutral above `CrmClient` and does not require a paid enrichment API.

## Future Sprints

### Sprint 23 - End-to-End Live Demo Runbook

Goal: make the local demo presentable and repeatable for a live walkthrough after the dashboard workflow sprints are complete.

#### User-facing workflow

- Add a concise runbook for starting, resetting, validating, and presenting the demo.
- Define the walkthrough from a fresh local stack: open overview, inspect events and incidents, add or edit an event, queue an event participant for enrichment, corroborate and promote an incident company to the watchlist, open a Watchlist Item, run or fake contact discovery, review analyst queue data, export to CRM, import or assign a prospect to a sequence, show sequence definitions, book or update meeting handoff, inspect meeting prep, and verify source health.
- Document which operator role to use for each step, including viewer read-only behavior, analyst/admin mutations, and governance-only metadata visibility.
- Document the expected visible state before and after each mutation so presenters can tell whether the demo is healthy.

#### Implementation notes

- Keep the runbook focused on local Docker Compose and deterministic fake data, not Kubernetes or production deployment.
- Require `demo_check.sh` to prove migrations, fake data, reporting APIs, console loading, Dash navigation, and representative mutation paths work.
- Extend demo validation to cover the newly planned Global Events, Global Incidents, Watchlist Item, Analyst Review, Sequence Definitions, and Meeting Detail workflows.
- Include recovery instructions for common local demo failures such as missing migrations, empty seed data, broken dashboard callbacks, failed gateway readiness, or unavailable fake external adapters.

#### Acceptance

- A new developer can complete the local live demo without manual database edits or ad hoc API calls.
- The runbook verifies the Global Events, Global Incidents, Watchlist, Analyst Review, Sequence State, Meetings, CRM export, meeting handoff, and source-health paths in order.
- `demo_check.sh` or the documented validation steps fail clearly when migrations, seed data, gateway/reporting APIs, dashboard callbacks, fake external adapters, or key mutation paths are broken.
- The live demo script shows governance-only metadata with a governance reviewer and confirms the same metadata is hidden from non-governance roles.

## Local Demo Acceptance Scenarios

- Fresh Compose stack from empty volumes.
- Migration bootstrap creates public tables.
- Gateway reporting endpoints return `200`, not `500`.
- Reset and reseed fake data.
- All dashboard tabs navigate correctly.
- Detail links resolve for seeded records.
- Dashboard actions mutate demo records and refresh visible state.
- Viewer role cannot mutate; analyst/admin role can mutate.
- Demo check fails clearly when migrations, seed data, or dashboard callbacks are broken.

## Local Demo Assumptions

- Use `SPRINTS.md`, not a new `SPRINT.md`.
- Fake data is acceptable and must be deterministic.
- The demo target is local Docker Compose, not Kubernetes or production.
- The first implementation priority is fixing the missing migration/schema problem because it blocks all reporting-backed dashboard pages.
