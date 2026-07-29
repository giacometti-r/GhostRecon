# GhostRecon Sprint Tracker

## Current Stage

Stage: Sprint 24 production configuration, no-synthetic enforcement, and release gates complete; Sprint 25 identity and API-perimeter work is next. The local Compose stack now has repeatable reset, migration, linked deterministic fake data, dashboard workflow coverage, watchlist monitoring scheduling, sequence definition/import workflows, and health-check commands for validating a ready local demo without manual database commands.

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

### Sprint 24 - Production Configuration, No-Synthetic Guarantee, and Release Gates

- Replaced the legacy environment selector with published local, test, staging, and production runtime profiles plus explicit service/provider enums.
- Added service-scoped startup validation, structured redacted issues, preflight CLI/Make target, named readiness checks, and validation before API, Celery, migration, and demo initialization.
- Restricted deterministic adapters, domain inference, and seeding to local/test boundaries; added strict adapter injection and persistence guards for synthetic provider/lineage markers.
- Added Helm profile rendering, per-workload secret-key projection, service-scoped preflight hooks, and strict SHA-256 image validation with positive and negative render coverage.
- Split CI into quality, migration/integration, Chromium browser, Helm evidence, Trivy image scan, and SPDX/CycloneDX SBOM jobs; added protected staging no-op/read-only provider evidence.
- Fixed the 26 visible MyPy failures and the Bandit OAuth constant finding without new ignores or widened exclusions.
- Published ADR, architecture, operations, Helm/secrets, Kubernetes, root, and per-service runtime documentation.

## Baseline Acceptance Criteria

- `make test` passes in a fully provisioned Python environment.
- `docker compose up --build` starts the implemented local stack.
- `make helm-check` validates bundled and external datastore manifests.
- Every documented service has a local `README.md` and `TECHNICAL_README.md`.
- The runtime baseline remains provider-neutral above `CrmClient` and does not require a paid enrichment API.

## Future Sprints

### Sprint 25 - OIDC Identity, Server-Side RBAC, and Secured API Perimeter

#### Objective and production outcome

Replace caller-asserted demo identity with OIDC users, signed service identity, and one authoritative server-side permission model across console, gateway, owner services, system endpoints, and audit.

#### Current implementation and dependencies

- src/ghostrecon/common/security.py has static token comparison but no application-wide middleware.
- Routers under src/ghostrecon/service_apps/routers/ accept caller-controlled X-Actor/X-Operator-Role; src/ghostrecon/console/ exposes and forwards demo roles. Authorization differs across callbacks, reporting, mutations, metrics, docs, and owner APIs.
- Requires Sprint 24 validation for issuer/client/session/service credentials. Local role selection may remain only behind a local/test backend impossible to start in staging/production.

#### Implementation and interface requirements

- Implement OIDC authorization-code flow with state, nonce, and PKCE. Store browser authentication in bounded, rotated, secure, HTTP-only, same-site sessions.
- Validate API JWT algorithm/signature, issuer, audience, expiry, not-before, subject, and required claims against trusted metadata with safe key rotation.
- Derive actor, subject, email, and roles only from verified claims. Reject external actor/role headers; permit normalized forwarding only from authenticated trusted services.
- Centralize permissions for viewer, analyst, governance reviewer, administrator, and named service identities. Cover every read, mutation, bulk/source action, governance field, metrics/docs, and system endpoint.
- Authenticate service-to-service calls; owner APIs accept only gateway or explicitly authorized worker identities.
- Add CSRF, secure response headers, restrictive CORS, TLS ingress expectations, request-size limits, endpoint rate limits, and explicit production metrics/docs policy.
- Audit allowed and denied privileged actions with verified identity, permission, resource, correlation, and outcome, without tokens or unnecessary claims.
- Publish login/callback/logout/session-expiry routes, normalized internal identity context, claim/role mapping, scopes/audiences, issuer/JWKS/session settings, and consistent 401 versus 403 semantics. Persist only necessary session/security-audit state, never raw tokens.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Never trust client-supplied identity, weaken issuer/audience validation, or log tokens/codes/cookies. V1 remains single-workspace; multi-tenancy is excluded.
- Test missing, expired, future, wrong-audience/issuer/signature/algorithm/key, malformed tokens, and key rotation.
- Generate a permission-matrix test for every route and protected endpoint. Prove spoofed actor/role/forwarding headers cannot affect authorization or audit identity.
- Add browser tests for login/logout, callback validation, CSRF, session expiry, viewer limits, governance-only data, and denied UX.
- Prove direct unauthenticated owner-service calls fail and every denied privileged operation creates a redacted traceable audit record.
- Acceptance: identity is verified cryptographically, all authorization is server-side, every exposed route is in the matrix, and privileged success/denial is safely auditable.

#### Documentation requirements

- Update affected root README, architecture, dashboard specification, runbook, gateway/console and owner-service docs, Helm README/secrets guide, and an ADR for OIDC, sessions, propagation, service auth, and RBAC.
- Apply Sprint 24's complete scoped documentation rule, completion update, historical-research preservation, and final consistency search.

### Sprint 26 - Source Operations Control Plane and Durable Source Scheduling

#### Objective and production outcome

Make the persisted source registry an operable control plane and continuously schedule eligible event/incident sources without manual task or database intervention.

#### Current implementation and dependencies

- SourceDefinition in src/ghostrecon/models/db/sources.py stores adapter, polling/rate policy, checkpoint, freshness, retry budget, policy, and operating state; contracts begin in src/ghostrecon/models/api/source_contracts.py.
- source_registry.py, source_adapters.py, workers.py, and worker_runtime.py can fetch/parse one source, but beat schedules watch monitoring rather than every due source. Reporting/console health is read-only while the runbook describes unsupported pause/replay/acknowledge actions.
- Requires Sprint 24 profiles and Sprint 25 identity/audit. Preserve checkpoints/policy; Sprint 27 consumes lifecycle events but is not needed for scheduling.

#### Implementation and interface requirements

- Add governance-controlled list, inspect, create, update, enable, pause, resume, test, run-now, acknowledge-error, and bounded-replay APIs plus matching console controls.
- Require optimistic versions and idempotency keys on mutations; replay/policy changes require confirmation, reason, and audit.
- Query persisted due enabled sources by interval/next-run state. Use distributed finite leases so one source/checkpoint has at most one active fetch.
- Enforce per-source concurrency, request rate, retry budget, exponential backoff/jitter, timeouts, size/crawl bounds, and failure isolation.
- Persist raw data before atomically advancing a normal checkpoint. Support conditional requests; keep replay watermarks separate and never move normal checkpoints backward.
- Keep policy fail-closed: unreviewed/prohibited sources may be connectivity-tested with quarantined output but cannot feed downstream work.
- Add versioned /v1/intelligence/sources collection/detail/action/run-history contracts exposing optimistic version and permitted actions.
- Persist source runs with source/version, trigger, verified actor, idempotency/correlation, checkpoint/replay range, HTTP validators, counts/timing/status/attempt, and redacted failure.
- Emit versioned requested/started/succeeded/failed/paused events with correlation, causation, source definition/run/item lineage. Report lag, next run, active lease, latest success/failure, retry exhaustion, and policy/operating state.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Never crawl outside allowlists/limits, publish test-run output, bypass policy/robots/terms, or allow unbounded replay.
- Unit-test due selection, clock boundaries, versions/idempotency, locks, atomic checkpoints, validators, retry/rate limits, pause/resume, ack, and replay.
- Database/broker tests cover concurrent schedulers, scheduler-to-worker execution, crashes, durable ingestion before checkpoint, and poison-source isolation.
- Contract/browser tests cover all actions, role limits, confirmation, stale versions, and status refresh.
- Acceptance: sources run continuously; operators need no database edits; replay cannot regress checkpoints or duplicate raw items; run/event/reporting state is durable and correlated.

#### Documentation requirements

- Update affected architecture, pipeline/dashboard specs, runbook, root README, ingestion/event/incident/reporting/console/gateway/governance docs, and Helm docs if scheduler/queue/topology changes.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 27 - Transactional Outbox Dispatch and Automated Pipeline Orchestration

#### Objective and production outcome

Turn persisted outbox intent and task islands into a reliable, observable, idempotent pipeline that advances real records automatically until an explicit human or policy gate.

#### Current implementation and dependencies

- Workflows write OutboxEvent rows, primarily modeled in src/ghostrecon/models/db/governance.py, but no dispatcher claims/publishes them. Persistence mainly exposes published_at, without full lease/retry/dead-letter state.
- src/ghostrecon/workers.py and worker_runtime.py expose ingestion, parsing, enrichment, scoring, governance, CRM, sequencing, and meeting tasks as callable islands; due sequence and inbound-mail work is unscheduled.
- Requires Sprints 24-26 and Sprint 25 service identities. Existing approval boundaries remain authoritative.

#### Implementation and interface requirements

- Add available time, lease owner/expiry, attempt, last error, published time, terminal status, and dead-letter/replay metadata plus indexed bounded due claims.
- Claim batches transactionally with concurrent-safe database locking and finite recoverable leases. Publish to explicit queues and mark delivery only after broker acceptance.
- Add capped backoff/jitter, poison isolation, dead-letter inspection/metrics, authorized replay, and immutable original lineage.
- Implement versioned idempotent consumers for source ingestion, event/incident parsing, resolution, scoring, review creation, CRM, sequences, inbound mail, and meetings.
- Encode the automatic-versus-analyst/governance/CRM/outreach/meeting transition table. Never infer export, enrollment, or sending from upstream approval.
- Propagate request/correlation, causation, schema, source-definition/run/item, and outbox IDs through rows, messages, tasks, and logs.
- Schedule due sequence steps, inbound mail, retryable CRM, and meeting sync with workload isolation.
- Migrate outbox state and add a consumer inbox/idempotency ledger where needed. Publish envelope schemas, compatibility, ownership, routing/queue/dead-letter topology, size limits, and retention.
- Add authorized dead-letter/stalled-work inspect/replay APIs with optimistic/idempotent mutations and audit. Report oldest outbox age, due/leased/retry/dead counts, queue age/depth, failures, and stage lag.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- At-least-once transport is expected; do not claim exactly-once. Replay cannot mutate originals, bypass current policy/approval, or duplicate canonical/external outcomes. Redact sensitive payloads.
- Test crash before/after broker acceptance, lease expiry/renewal, concurrent claims, duplicates, poison, retry exhaustion, broker outage, version rejection, ordering, and replay.
- Add event-contract tests and a real database/broker end-to-end test from raw item to the correct review queue.
- Replay every supported event and prove canonical/external operation plans remain duplicate-free; dead letters must be operable without database access.
- Acceptance: committed intent is published or terminally dead-lettered with evidence; all consumers are versioned/idempotent; real data advances automatically only to the correct gate; lag is measurable.

#### Documentation requirements

- Update affected architecture, pipeline spec, runbook, producer/consumer docs, event/queue technical docs, and Helm topology/configuration.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 28 - Live Cybersecurity Event and Participant Acquisition

#### Objective and production outcome

Acquire useful real cybersecurity events and permitted participant evidence from official sources through one bounded, lineage-complete scheduled/manual pipeline.

#### Current implementation and dependencies

- Seeded DEF CON, Black Hat, BSides, OWASP, and FIRST sources use generic http_page extraction, retaining mostly title/description and producing unknown dates, timezone, venue, or format.
- Participant extraction in src/ghostrecon/services/event_intelligence/ works mainly for Schema.org data. NOTES.txt requests scraping a manually supplied event URL.
- Requires Sprints 24 and 26-27 for safe live configuration, scheduling, and orchestration, plus Sprint 25 actor/governance controls.

#### Implementation and interface requirements

- Add source-specific extraction using Schema.org, ICS, RSS, bounded HTML traversal, and source-owned selectors only where structured formats are absent.
- Extract canonical name/URL, local dates/timezone and UTC instants, venue/structured address, format/virtual URL, topics, organizers, speakers, sponsors, and permitted public profiles.
- Manual URL submission must enqueue the same fetch/parse workflow and preserve manual actor, submitted URL, source run/item, parser version, and correlation lineage.
- Discover detail/participant pages only within allowlisted domains, depth/page/size/time budgets, robots/terms policy, and configured reuse permission.
- Persist parser version, extraction diagnostics, selector/structured-format path, missing-field reasons, and drift state.
- Maintain real-shape fixtures and bounded protected staging canaries for every official source. Merge duplicate editions without deleting source lineage.
- Geocode structured addresses through configured Nominatim-compatible service with cache, identification user agent, rate limit, and reviewable failures.
- Participant reuse evidence must be reviewed before contact extraction or CRM eligibility.
- Extend event/source contracts and persistence for timezone, UTC timestamps, structured venue/address, format, cancellation/reschedule/series identity, participants, parser metadata, diagnostics, and lineage. Reporting exposes parse yield/drift and missing required fields.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Do not crawl outside allowlists, treat unknown reuse as permission, infer unpublished dates/locations, or use unstable live text as deterministic CI evidence.
- Fixture tests cover every source plus degraded/malformed pages, timezone/DST, recurring series, cancellations/reschedules, hybrid events, duplicate editions, participant reuse, and geocoding limits/cache.
- Contract/integration tests prove scheduled and manual submissions share pipeline/event schemas and lineage. Browser tests cover manual URL status, diagnostics, merge/review, and roles.
- Bounded staging canaries fetch official sites without asserting presentation text.
- Acceptance: scheduled sources create real events with dates and location/format whenever published; manual ingestion has identical parser/lineage metadata; no participant enters enrichment with unknown/prohibited reuse.

#### Documentation requirements

- Update affected event-intelligence, ingestion, enrichment, reporting, console, gateway, governance docs; architecture, pipeline/dashboard specs, runbook, and root README. Document supported sources, extraction strategies, policy, and drift recovery.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 29 - Live Incident, Advisory, and Watchlist Intelligence

#### Objective and production outcome

Continuously acquire trustworthy incident, advisory, vulnerability, and watch signals while preserving company-specific evidence, source independence, and uncertainty.

#### Current implementation and dependencies

- GDELT, CISA news RSS, and The Hacker News are seeded; CISA KEV/NVD clients exist outside scheduled canonical workflows.
- Company extraction relies heavily on metadata/regex. Syndicated copies may appear independent. SerpAPI watch monitoring exists but lacks complete production configuration/data-quality operation.
- Requires Sprints 24, 26, and 27; uses Sprint 25 identity and Sprint 28's source/parser operational patterns.

#### Implementation and interface requirements

- Schedule GDELT, CISA advisories/RSS, trusted RSS, CISA KEV, NVD, and SerpAPI watch queries through the registry with durable checkpoints, quotas, deduplication, and evidence retention.
- Treat CVE/advisory items as security signals unless evidence identifies an affected organization; never fabricate a company incident from a vulnerability.
- Resolve companies/domains using publisher metadata, verified domains/accounts, evidence URLs, and preserved alternative matches routed to review.
- Persist publisher identity, canonical/original URL, syndication cluster, evidence family, authoritative status, independence, language, and explicit translation provider/version/lineage.
- Split evidence-supported multi-company incidents into company-specific canonical rows linked to one incident group; leave unsupported incidents unassigned.
- Corroboration requires authoritative disclosure, genuinely independent sources, or an audited analyst decision. Route ambiguity, stale evidence, and insufficient corroboration to review.
- Extend signal/incident/watch contracts and persistence for groups, candidate companies, publisher/syndication/independence, language/translation, corroboration decision, watch watermark/quota, and evidence lineage. Reporting exposes provider/source degradation and watermarks.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Do not equate repetition with independence, translate without provenance, assign a company from weak name coincidence, or promote stale/uncorroborated evidence automatically.
- Add real-shape fixtures for GDELT, CISA RSS/advisories, KEV, NVD, trusted news, syndicated copies, multilingual metadata, and SerpAPI.
- Test ambiguity, false-positive rejection, multi-company splitting, syndication clusters, independence, time-window dedupe, translations, checkpoint/quota behavior, and outages.
- Add bounded staging canaries for each provider and browser/contract tests for review, evidence, watch status, and governance decisions.
- Acceptance: incidents are company-specific only when supported, otherwise unassigned; syndicated copies never satisfy independence; watch watermarks advance durably and degradation is visible.

#### Documentation requirements

- Update affected incident/ingestion/enrichment/scoring/governance/reporting/console/gateway docs plus architecture, pipeline/dashboard specs, runbook, and root README. Document classification, corroboration, watches, multilingual provenance, and false-positive recovery.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 30 - Production Entity Resolution, Contact Enrichment, and Email Verification

#### Objective and production outcome

Resolve organizations and contacts from observed, permitted evidence; operate crawl/search/verifier dependencies; and eliminate synthetic discovery from live enrichment.

#### Current implementation and dependencies

- OpenSERP adapters support official-domain and LinkedIn discovery, but live participant enrichment can fall back to an invented domain.
- The Scrapy company crawler does not return/persist discoveries through the canonical workflow. Persistence-backed resolution has limited real evidence/alternatives. The verifier sidecar is callable but not fully operated.
- Requires Sprints 24 and 27, consumes event/incident evidence from Sprints 28-29, and respects Sprint 25/26 policy and controls.

#### Implementation and interface requirements

- Remove synthetic domain inference from all non-demo workflows. Use OpenSERP for official sites and permitted professional profiles, persisting query, rank, URL, snippet, provider, retrieval time, and lineage.
- Validate selected corporate domains through redirect chain, registrable-domain/public-suffix normalization, website identity signals, DNS evidence, and suspicious-domain checks.
- Persist crawler discoveries and feed canonical candidates; retain multiple plausible organizations/domains and route ambiguity to analyst review.
- Enforce allowlists, robots/terms policy, crawl budgets, prohibited sources, timeouts, and content-retention limits.
- Generate email candidates only from verified domains and person names with permitted lineage. Batch verifier calls with health, bounded concurrency/retries, and explicit valid/invalid/catch-all/ambiguous/unknown outcomes.
- Learn organization email patterns only from verified evidence; a generated pattern match is never itself verification.
- Extend candidate/evidence contracts and persistence for observed versus generated origin, search/crawl/DNS/redirect lineage, alternatives, selection decision, verifier provider/attempt/outcome, and pattern evidence. Expose provider health and ambiguity through reporting/review UI.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Never present generated domains/profiles/emails as observed provider data, crawl denied sources, or classify pattern-only addresses as verified.
- Prove missing domains stay missing when discovery fails. Test suspicious/conflicting domains, redirects, public suffixes, outages, denied crawl, budgets, catch-all, verifier timeout/retry, and ambiguous alternatives.
- Add OpenSERP/verifier contract tests, database workflow tests, browser review tests, and bounded staging canaries with protected credentials.
- Acceptance: a real participant/watch target reaches review with complete search/crawl lineage; all candidate origins are explicit; absence and ambiguity remain honest.

#### Documentation requirements

- Update affected enrichment, email, event, incident, scoring, governance, reporting, console, gateway docs plus architecture, pipeline/dashboard specs, runbook, public-enrichment ADR, and root README.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 31 - Attio Provisioning, Export, Reconciliation, and Webhook Operations

#### Objective and production outcome

Operate Attio as the approved sales-record system with preflighted schema, idempotent export, authenticated webhooks, continuous reconciliation, and visible drift.

#### Current implementation and dependencies

- CrmClient implementations in src/ghostrecon/services/crm_attio.py and crm_exports/ support Attio export/search and idempotent batch planning, but assume objects, attributes, and lists exist.
- There is no continuous reconciliation or authenticated webhook intake; credentials can fail late without Sprint 24.
- Requires Sprints 24-25 and 27; consumes approved records from Sprint 30. CRM export remains distinct from outreach approval.

#### Implementation and interface requirements

- Add read-only schema preflight for required objects, attributes, lists, permissions, workspace identity, and supported API capabilities.
- Add an explicitly invoked administrator-only provisioning/migration plan and apply operation only where supported; preview changes and require version/idempotency/confirmation/audit.
- Persist provider configuration version and workspace identity with batches/items.
- Add signed webhook intake for supported record/list changes, verify timestamp/signature/workspace, retain provider event IDs, and prevent replay.
- Schedule reconciliation for missing records, changed stable IDs, partial list membership, and meeting/outcome drift; make each discrepancy visible and repairable.
- Coordinate read/write rate limits across replicas, honor retry metadata, classify terminal/retryable failures, expose token health/rotation/circuit/degraded state.
- GhostRecon remains authority for intelligence lineage/approval; Attio remains authority for approved sales records. Export never grants outreach approval or sequence enrollment.
- Publish preflight/provision/reconcile/webhook contracts, webhook event/version rules, reconciliation state, provider workspace/config fields, and authorized repair APIs.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Provisioning is never automatic at startup; reject invalid signatures, stale/replayed events, and wrong workspaces. Never overwrite intelligence lineage from provider data.
- Contract tests cover preflight, provisioning plans, upserts/list entries, pagination/rates, webhook signature/replay/workspace, reconciliation, circuit, and rotation.
- Database/integration tests prove retries/reconciliation are idempotent; browser tests cover preflight, drift, repair, roles, and degradation.
- Use an isolated staging workspace for bounded live acceptance.
- Acceptance: repeats create no duplicate people/companies/custom objects/list entries; drift is visible/repairable without database edits; export cannot activate outreach.

#### Documentation requirements

- Update affected CRM, governance, reporting, console, sequencing-import, meeting, gateway docs plus architecture, pipeline/dashboard specs, runbook, Attio ADR, Helm secrets guide, and root README.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.
+
### Sprint 32 - Production Sequencing, Mail Delivery, and Google Calendar Handoff

#### Objective and production outcome

Operate approved outreach and meeting handoff with at-most-once business outcomes, durable mailbox state, sender readiness, and reconciliation across SMTP/IMAP, Google Calendar, and Attio.

#### Current implementation and dependencies

- SMTP/IMAP adapters exist in src/ghostrecon/services/sequence_adapters.py; due-step and inbound-poll tasks exist but are not scheduled. IMAP relies on UNSEEN and simple sender/subject classification.
- Google Calendar service-account support and a fake fallback live under src/ghostrecon/services/calendar_adapters/; sender-domain readiness, durable mailbox checkpoints, and provider reconciliation are incomplete.
- Requires Sprints 24-25, 27, 30, and 31. Meeting booking, CRM export, and outreach approvals remain independent.

#### Implementation and interface requirements

- Run due-step and inbound-mail schedules through Sprint 27 orchestration, isolating sender, mailbox, sequence, and provider failures.
- Persist mailbox checkpoints and stable message/provider IDs independently of UNSEEN. Correlate replies/bounces with Message-ID, In-Reply-To, References, envelope/provider IDs, and stored outbound lineage.
- Add bounded retries, timeout/error classes, terminal delivery states, operator-visible recovery, and transactional/idempotent send claims.
- Immediately before send, re-evaluate current verification, lawful basis, outreach approval, suppression, evidence freshness, sequence/sender limits, and unsubscribe requirements.
- Validate SPF, DKIM, DMARC, envelope sender, reply mailbox, unsubscribe configuration, and provider identity before enabling a sender.
- Reconcile Google Calendar create/update/cancel via stable meeting IDs; validate credentials and delegated access at meeting-service startup/readiness.
- Extend sender/mailbox/message/delivery/meeting contracts and persistence for readiness, checkpoints, provider IDs, correlation, attempts, terminal state, bounce/reply classification, suppression action, and reconciliation drift.
- Provide authorized retry/reconcile controls and reporting for delivery/mailbox/calendar health without exposing message bodies or credentials.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Never send without fresh approval/policy checks, use UNSEEN as the sole checkpoint, treat auto-replies as positive replies, or couple booking/export/outreach approval.
- SMTP/IMAP integration tests use isolated servers/sandboxes and cover duplicate/rescanned messages, delayed bounces, auto-replies, unsubscribe, suppression races, sender limits, timeouts, and worker crashes.
- Google Calendar contract tests cover authentication, delegated access, booking, free/busy, update/cancel, rates, reconciliation, rotation, and outages. Add browser recovery/status tests.
- Acceptance: approved outbound email sends at most once; inbound state changes at most once across polls; booked meetings reconcile consistently across GhostRecon, Google Calendar, and Attio.

#### Documentation requirements

- Update affected sequencing, email, meeting, CRM, governance, reporting, console, gateway docs plus architecture, pipeline/dashboard specs, runbook, Helm README/secrets guide, and root README.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 33 - End-to-End Observability, Data Quality, and Incident Response

#### Objective and production outcome

Give operators one correlation entry point to trace real data across HTTP, database, scheduler, outbox, workers, and providers, with actionable quality/availability signals and safe recovery procedures.

#### Current implementation and dependencies

- Basic Prometheus request count/latency exists and OpenTelemetry packages are installed, but tracing is incomplete. Structured logs do not consistently bind context across HTTP, Celery, outbox, SQL, and providers.
- The runbook names queue/outbox/projection/source-quality metrics not fully emitted; readiness often checks only schema availability.
- Requires Sprints 24-32 so all production workflows expose stable identifiers and operational states.

#### Implementation and interface requirements

- Instrument FastAPI, SQLAlchemy, Celery, Redis, outbox dispatch, source scheduling, and outbound HTTP clients with OpenTelemetry and consistent sampling/export failure behavior.
- Propagate request, correlation, causation, source-run/item, outbox/message, provider-operation, CRM, mail, and meeting identifiers across all boundaries.
- Emit API RED metrics and bounded-cardinality workflow metrics for sources/parsers, queues/outbox, review, providers, mail, CRM, and meetings.
- Emit quality metrics for parse yield, required-field completeness, duplicates, suspicious domains, resolution ambiguity, and corroboration quality, with defined denominators.
- Add service-specific readiness for mandatory local dependencies; remote provider health affects degraded state, not liveness.
- Add alerts with severity, owner, threshold/window, investigation, safe mitigation, escalation, and recovery evidence.
- Redact tokens, email content, prohibited personal data, article bodies, and provider secrets from logs/traces/metrics.
- Add parser-drift canaries that can pause only unsafe sources while independent pipelines continue.
- Publish trace/log field and metric contracts, cardinality budgets, readiness/degraded schemas, dashboards, alert ownership, and correlation search/reporting entry points.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Never use unbounded IDs/URLs/emails as metric labels, expose sensitive payloads, or make liveness depend on remote providers.
- Test trace propagation across HTTP/outbox/worker/database/provider, sampling context, label cardinality, redaction, readiness, and telemetry-export outages.
- Exercise alerts for stale source, backlog, dead letter, provider outage, parser drift, CRM drift, mail failure, and calendar failure; conduct documented recovery drills.
- Deployment tests prove one provider/source outage degrades only dependent workflows.
- Acceptance: an operator traces one real record end-to-end from one correlation entry point; alerts are actionable/owned; sensitive data is absent from telemetry.

#### Documentation requirements

- Update affected architecture, runbook, Helm docs, service user/technical docs for metrics/traces/logs/health/readiness/alerts, and pipeline/dashboard specs where state becomes visible.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 34 - Privacy, Retention, Policy Administration, and Tamper-Evident Audit

#### Objective and production outcome

Make policy authoritative and versioned, automate retention and data-subject workflows, enforce legal holds, and detect audit-log tampering across GhostRecon and provider references.

#### Current implementation and dependencies

- Governance under src/ghostrecon/services/governance/ checks suppression, lineage, reuse, lawful basis, evidence age, and snapshots, but some policy values are caller-supplied rather than resolved from an authoritative store.
- There is no complete retention, data-subject request, anonymization, legal-hold, or audit-integrity workflow; audit rows are not tamper-evident or externally anchored.
- Requires Sprints 25 and 27 plus persisted lineage/provider states from Sprints 28-33.

#### Implementation and interface requirements

- Add authoritative versioned policy records for source permission, lawful basis, participant reuse, retention, suppression, approval, and outreach eligibility, with effective dates and immutable hashes.
- Resolve policy server-side at decision time and persist exact version/hash. Caller snapshots are advisory input only and cannot override authority.
- Add administrator/governance policy APIs with optimistic versions, idempotency, effective dates, preview/validation, permissions, and complete audit history.
- Add retention evaluation and deletion/anonymization jobs for raw items, evidence, contacts, email payloads, and provider responses. Preserve only legally required minimal suppression identifiers.
- Add data-subject request intake, identity/authorization verification, discovery, export, restriction, deletion, provider action/reference tracking, and completion evidence.
- Add scoped legal holds preventing deletion while allowing reporting of held-expired data.
- Hash-chain or sign audit entries, protect signing keys, periodically verify continuity/signatures, and anchor summaries externally when configured.
- Add governance reports for violations, retention failures, stale evidence, prohibited reuse, unauthorized activation attempts, subject-request status, holds, and audit integrity.
- Publish policy/DSR/hold/integrity APIs and event schemas, migrations, retention schedules, deletion/anonymization semantics, provider coordination, signature/key rotation, and failure recovery.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Do not accept favorable caller policy, delete held data, erase required suppression protection, expose one subject's data to another, or rewrite audit history.
- Test policy-version races/retroactivity, effective boundaries, retention clocks, holds, cascades, anonymization, suppression preservation, signing/key rotation, altered/missing audit entries, and job crashes/retries.
- End-to-end DSR tests span canonical records, CRM references, sequencing, meetings, raw evidence, provider actions, and audit evidence. Browser/contract tests cover all admin/governance roles and optimistic conflicts.
- Acceptance: callers cannot bypass policy; expired data is removed/anonymized on schedule while holds remain; DSRs produce complete evidence; integrity verification detects alterations and gaps.

#### Documentation requirements

- Update affected governance, ingestion, enrichment, email, scoring, CRM, sequencing, meeting, reporting, console, gateway docs plus architecture, pipeline/dashboard specs, runbook, relevant ADRs, secrets guide for signing keys, and root README.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 35 - Kubernetes Production Platform, Disaster Recovery, and Go-Live

#### Objective and production outcome

Deliver a hardened Kubernetes/Helm production profile with recoverable data services, workload-aware scaling, immutable promotion, tested failure recovery, and evidence-based go-live approval.

#### Current implementation and dependencies

- deploy/helm/ghostrecon/ deploys APIs, one worker, one scheduler, bundled PostgreSQL/Redis, and CPU-based API HPAs.
- TLS ingress, application network policies, disruption budgets, topology spreading, workload autoscaling, backups, and tested restore/regional recovery are absent. Secrets remain SOPS/Age placeholders; no load/soak/rollback evidence proves readiness.
- Requires completion of Sprints 24-34. Kubernetes/Helm is production; Compose remains local/pilot troubleshooting.

#### Implementation and interface requirements

- Recommend managed PostgreSQL/Redis for production while retaining bundled stores only for local/pilot profiles; make durability/HA capability differences explicit and validated.
- Add TLS ingress, restrictive application network policies, pod disruption budgets, anti-affinity/topology spreading, least-privilege service accounts/RBAC, security contexts, and resource budgets.
- Separate queues/workers by workload and scale by queue lag/work metrics rather than API CPU alone. Guarantee one active scheduler through leader election or equivalent durable scheduling.
- Add PostgreSQL backups, PITR, automated restore verification, and migration rollback/roll-forward procedures. Define Redis persistence/recovery for its queue/coordination role.
- Enforce immutable image provenance/signing, vulnerability policy, SBOM linkage, secret rotation, and controlled environment promotion.
- Add load tests for APIs, ingestion, outbox, review, CRM batching, sequence scheduling, and reporting; add failure injection for pod loss, broker outage, database failover, provider timeout, scheduler restart, and partial deployment.
- Run a bounded staging burn-in with real sources/provider staging accounts and no synthetic inputs.
- Define measurable SLIs/SLOs, RPO/RTO, capacity, ownership/on-call, launch and rollback criteria, deployment waves, and post-launch monitoring.
- Publish Helm values/contracts for managed/bundled profiles, queue topology/autoscaling, ingress/network policy, backups, probes, identities, secret references, and promotion. Do not embed credentials.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Do not present bundled stores as HA production, scale schedulers without singleton guarantees, use mutable artifacts, expose services through permissive policies, or count synthetic data as burn-in evidence.
- Helm lint/render tests cover managed and bundled profiles, TLS, policies, identities, scaling, and invalid combinations.
- Migration tests cover upgrade, failed recovery, supported rollback, and forward-fix. Restore/regional drills demonstrate documented RPO/RTO.
- Load/soak tests meet latency, throughput, freshness, and queue-lag SLOs; failure injection proves dependent-only degradation and safe recovery.
- Go-live requires successful security, recovery, load, staging-soak, and real-data end-to-end exercises with signed owners and explicit rollback criteria.
- Acceptance: production topology is hardened and observable, data recovery meets objectives, deployment is promotable/rollback-capable, and outages remain isolated.

#### Documentation requirements

- Update affected root README, architecture, runbook, Helm README/secrets guide, and deployment/operations sections of service docs changed by topology, dependencies, scaling, probes, recovery, or ownership. Update PRESENTATION.md only if its deployment/readiness claims become inaccurate.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

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
