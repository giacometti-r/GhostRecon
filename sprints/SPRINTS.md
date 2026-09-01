# GhostRecon Sprint Tracker

## Current Stage

Stage: Sprint 25a security-foundation primitives are implemented and covered by focused unit tests; Sprint 25b production identity, workload trust, active RLS, and perimeter integration is next, followed by Sprint 25c shared-SaaS tenant isolation and privileged-support controls. The current gateway and console still use legacy local/test identity flows, while strict staging/production profiles reject caller-supplied identity headers before replacement OIDC and service-authentication middleware exists. GhostRecon remains local/synthetic-only: do not process real personal data, enable live providers, install production credentials, expose services externally, or market the runtime as enterprise-ready until the applicable enterprise security release gates below pass with recorded evidence.

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

### Sprint 25a - Security Foundation Primitives

- Added immutable normalized human/service/worker identity context, additive viewer/analyst/governance-reviewer/administrator permissions, assurance checks, recent-authentication checks, and default denial for unknown roles.
- Added Ed25519 service-token and 45-second operation-bound on-behalf-of claim helpers plus strict issuer, subject, audience, purpose, lifetime, key-ID, and signature validation primitives.
- Added generic RSA OIDC metadata, PKCE S256 transaction, safe return-path, bounded JSON/JWKS, and ID-token validation helpers without adding production login, callback, discovery, or session repositories.
- Added opaque session and CSRF secret generation using 256-bit-or-stronger HMAC keys and host-only cookie names.
- Added the initial code-owned `OperationPolicy` registry for authentication, session, security administration, audit, health, readiness, metrics, and documentation operations. The registry is declarative and is not yet bound to the route set.
- Added application-wide transport perimeter middleware with correlation IDs, declared body/header/query bounds, reserved-header rejection in staging/production, and security response headers. It does not implement authentication, authorization, CSRF, CORS, distributed rate limiting, trusted-proxy validation, or chunked-body accounting.
- Added security principal, role-binding, session, emergency-grant, replay-marker, and policy-version models, expanded audit identity/decision columns, and transaction-local PostgreSQL security context helpers.
- Added migration `0015_security_foundation`. It creates three security-table/audit SELECT policies but intentionally does not enable or force RLS; its downgrade currently drops only those policies and is not a complete schema rollback.
- Added 14 focused unit tests for roles, assurance, immutable identity, internal JWT/OBO primitives, session secrets, OIDC validation, perimeter behavior, and the initial operation registry.
- Published the [security foundation reference](docs/security-foundation.md), [provisional ADR](docs/adr/0006-security-foundation.md), and [foundation evidence report](docs/reports/sprint-25a-security-foundation.md). The complete target requirements remain preserved in [SPRINT_25.md](SPRINT_25.md).

## Baseline Acceptance Criteria

- `make test` passes in a fully provisioned Python environment.
- `docker compose up --build` starts the implemented local stack.
- `make helm-check` validates bundled and external datastore manifests.
- Every documented service has a local `README.md` and `TECHNICAL_README.md`.
- The runtime baseline remains provider-neutral above `CrmClient` and does not require a paid enrichment API.

## Enterprise Security Release Gates

These gates are cumulative and override individual sprint language that otherwise permits live-provider or real-data acceptance. A sprint is not enterprise evidence merely because unit tests, Bandit, Ruff, MyPy, Helm lint, image scanning, or the local demo pass. Each control requires production-shaped negative tests and criterion-to-evidence reporting.

| Control | Current risk | Owner sprint | E1 live-data requirement | E2 enterprise-production requirement | Required evidence |
| --- | --- | --- | --- | --- | --- |
| Human authentication and operation authorization | Routes, sensitive reports, and mutations are not yet protected by verified identity and route-bound policy | 25b | Required | Required | Complete operation inventory; 401/403/step-up negative tests; no caller-controlled actor/role paths |
| Workload, owner-service, and task trust | Owner services and Celery work do not yet enforce distinct authenticated callers, signed delegation, or replay protection | 25b | Required | Required | Service-boundary and task-signature tests; key rotation; replay and wrong-audience rejection |
| Shared-SaaS tenant isolation | Only a default workspace identity field exists; domain records, sessions, caches, queues, integrations, and reports are not tenant-isolated | 25c | Required | Required | Forced-RLS and cross-boundary isolation suite for shared and dedicated placement |
| Database least privilege and RLS | Runtime roles share owner-capable database access; policies are not enabled or forced | 25b-25c | Required | Required | Non-owner roles, missing-context denial, forced CRUD RLS, pooled-connection cleanup, query-plan evidence |
| Authoritative verification and policy | Callers can currently supply favorable email-verification results and policy snapshots | 25b, 30, 34 | Minimum authoritative controls required | Complete policy administration, retention, DSR, holds, and integrity required | Forged-result/snapshot rejection and authoritative-version evidence |
| Provider transport and outbound-request safety | Mail TLS does not explicitly verify certificates/hostnames; source/crawl paths lack complete SSRF and response bounds | 26, 28-30, 32 | Required before each affected provider is enabled | Required | Invalid-certificate, private-address, redirect, rebinding, content-type, timeout, and size-limit tests |
| Rate, body, error, docs, and metrics perimeter | Chunked bodies, distributed rate limits, uniform redaction, protected system endpoints, and bounded path labels are incomplete | 25b, 33 | Required | Required | Abuse tests, streamed-body enforcement, protected docs/metrics, cardinality and redaction evidence |
| Privacy, audit, and privileged access | Audit identity/integrity fields, tenant-aware DSR/retention, and time-bounded support access are incomplete | 25c, 34 | Enforced identity/audit/support baseline required | Full privacy and tamper-evidence workflows required | Tenant-bound audit, support-grant expiry, DSR/hold, alteration/gap detection, compliance review |
| Platform, recovery, and software supply chain | Application NetworkPolicies, HA/restore evidence, reproducible dependencies, signed provenance, and product-security governance are incomplete | 35 | Staging-grade isolation and secret handling required | Required | Helm negative renders, SBOM/signature/provenance, vulnerability policy, restore/DR/load exercises, penetration test |

### E0 - Local and synthetic only

- Current state. Use deterministic local/test identities, providers, and data only.
- Docker Compose, bundled stores, public development ports, placeholder secrets, mutable local images, and local demo roles are never production patterns.
- No real personal data, production tenant data, customer credentials, live mail, live CRM, public-source crawling, externally reachable ingress, or customer-facing availability claim is allowed.

### E1 - Controlled live-data staging

- Complete Sprints 25b and 25c and the minimum authoritative verification/policy, provider TLS, outbound-request, audit, and perimeter controls in the matrix before any real personal data or live provider is enabled.
- Enable a provider only after its capability-specific gate passes: source/search/crawl requires outbound-policy and SSRF evidence; CRM requires tenant-bound credentials/workspace/webhook/reconciliation evidence; mail requires verified TLS and at-most-once delivery claims; calendar requires tenant-bound credentials and reconciliation.
- Use isolated staging tenants and provider sandboxes, bounded data, protected credentials, explicit data owners, retention limits, rollback criteria, and no production customer access.
- Require zero unresolved Critical findings, documented disposition of every High finding, and signed security/data-owner approval for the exact staging exercise.

### E2 - Enterprise production

- Complete Sprints 25b-35, including privacy/DSR/retention, tamper-evident audit, managed recovery, workload isolation, immutable promotion, and shared/dedicated tenant-placement evidence.
- Require zero unresolved Critical or High findings, an independent penetration test after the final security architecture is deployed, remediation verification, and an owner-signed residual-risk register.
- Require tested backup/PITR/restore and regional-recovery objectives, load/soak results, incident and vulnerability-disclosure processes, dependency/SBOM/provenance evidence, and explicit launch/rollback criteria.
- Local demo checks, deterministic providers, or scanner-only reports cannot satisfy E1 or E2.

## Future Sprints

### Sprint 25b - Complete Production Identity, Workload Trust, RLS, and Perimeter Rollout

#### Objective and production outcome

Finish the production integration left out of the Sprint 25 security-foundation implementation. Convert the implemented identity, RBAC/assurance, OIDC/JWT validation, session-secret, operation-policy, perimeter, security-table, audit, and database-context primitives into an end-to-end enforced architecture. Completion requires real gateway mediation, authenticated owner/worker boundaries, authoritative revocable sessions, complete route/table matrices, staged forced RLS, hardened deployment topology, and acceptance evidence.

#### Implemented foundation and explicit gaps

- Implemented: immutable normalized identity, additive human roles, assurance checks, Ed25519 service JWT/OBO primitives, generic RSA OIDC ID-token validation, opaque session/CSRF secret helpers, perimeter middleware, initial operation registry, security models, expanded audit columns, transaction-local database context, and additive migration `0015_security_foundation`.
- Missing: production login/callback/refresh/step-up/logout/session/user-administration/audit-query routes and their PostgreSQL/Redis repositories.
- Missing: gateway-to-owner HTTP proxying, gateway-only ingress, console reverse proxy, authenticated console-to-gateway calls, and removal of owner handlers from console/gateway processes.
- Missing: removal of caller-controlled identity headers, demo role UI/callback checks, static-token configuration, raw actor parameters, role-name comparisons, and `ReportingOperatorContext` defaults. Strict profiles currently reject these headers before a replacement identity flow is available.
- Current exposure: the generated gateway contract contains 51 mutation operations with no declared security scheme, while sensitive reporting can project contact email and meeting/attendee/provider data to an unauthenticated default viewer.
- Current integrity risk: unauthenticated callers can reach governance decisions, sequence enrollment/activity actions, and real provider side effects when business-state preconditions happen to pass.
- Missing: workload trust-bundle/key loading, request middleware, caller allowlists, replay storage, key rotation, OBO propagation, signed Celery delivery, and split worker identities/queues.
- Missing: complete operation/RLS matrices, database roles/grants, scope columns/backfills, CRUD policies, shadow validation, grouped RLS enablement, final `FORCE ROW LEVEL SECURITY`, and a complete reversible migration path for `0015`.
- Missing: CSRF enforcement, restrictive CORS, trusted-proxy/TLS handling, Redis rate limits, streamed-body/query/cookie bounds, Dash CSP, docs/metrics authorization, and uniform redacted errors. `/docs`, `/redoc`, `/openapi.json`, `/readyz`, and `/metrics` remain mounted without policy enforcement.
- Missing: deterministic local OIDC, Auth0 staging validation, Helm/NetworkPolicy/key/credential changes, browser/service/database integration tests, documentation, and criterion-to-evidence reporting.

#### Gateway OIDC and authoritative sessions

- Add gateway-owned login, callback, session, logout, logout-all, provider logout callback, reauthentication/step-up, role-claim refresh, security user/session administration, and audit-query routes.
- Fetch discovery/JWKS only from configured HTTPS issuers with five-second timeouts, one-MiB bounds, bounded caches, an asymmetric algorithm allowlist, rate-limited unknown-`kid` refresh, rotation overlap, and fail-closed behavior.
- Complete code exchange and validate state, nonce, PKCE S256, redirect URI, issuer, audience, authorized party, purpose, required claims, authentication method/time, and safe relative return paths. Never retain codes, provider tokens, OTPs, or raw claim sets.
- Store encrypted one-time OIDC transactions in Redis for ten minutes, atomically consume them, bind them to a separate host-only HttpOnly cookie, and test replay, supersession, expiry, browser binding, and open redirects.
- Implement PostgreSQL-authoritative opaque sessions containing only HMAC digests, with Redis cache subordinate to revocation. Enforce normal/remembered idle and absolute limits plus 15-minute rotation.
- Rotate atomically after login, step-up, privilege/policy/mapping changes, and periodically. Implement local and subject-wide logout, disablement, role/policy invalidation, self-service revocation, and step-up-protected other-user revocation.
- Recheck local provisioning/mapping on every request with no more than 60 seconds of disablement caching. Refresh provider role claims every five minutes; stale claims grant only session self-service.
- Require recent phishing-resistant assurance for governance decisions/overrides, bulk review, sensitive export, destructive work, security administration, role changes, and other-user session revocation.
- Add one-time administrator bootstrap and bounded emergency-grant CLI operations with verified issuer/subject, reason, approver evidence, expiry, step-up, and audit, with no bypass of RBAC/RLS/service authentication.

#### Gateway topology, authorization, and console migration

- Make `gateway-service` the sole ingress and reverse proxy `/` to internal `console-service`; keep console and owner services internal-only.
- Replace gateway decorator reuse/in-process owner execution with authenticated forwarding that preserves public `/v1/...` paths and schemas.
- Make Dash call gateway only through a console workload JWT and represented-user envelope; gateway independently reauthorizes and signs an owner-audience OBO envelope.
- Remove the role selector plus all `X-Actor`, `X-Operator-Role`, actor, and role propagation from clients, callbacks, routers, services, repositories, reports, audits, and task payloads.
- Replace role-name checks and reporting defaults with verified permissions and server-projected permitted actions. Add denied, expired, stale-role, and step-up-required UX.
- Classify every FastAPI route, Dash action, service operation, Celery task, CLI, docs/metrics/system endpoint, and auth/security action in one code-owned `OperationPolicy` registry.
- Generate operation and RLS matrices plus documentation; CI fails for missing/stale entries, duplicate IDs, unknown permissions/callers, missing tests, and unclassified routes/tables.
- Preserve public contracts while returning uniform redacted `code`, `message`, and `correlation_id` errors with consistent 401/403/existence-sensitive 404 semantics.
- Bind a required operation policy and verified identity dependency to every current and future route; CI compares the route inventory to the registry and rejects a route with no authentication, permission, assurance, caller, resource, body, and rate policy.
- Protect CRM targets, review queues, meetings, source health, KPI reports, exports, and record details against enumeration and IDOR; project fields only after server-side resource authorization.
- Remove the unused permissive static-token helper and bearer-token configuration rather than retaining a second authentication path. Strict profiles fail startup if legacy identity or unclassified routes remain.

#### Workload identity, replay, and worker isolation

- Load distinct Ed25519 private keys and trust bundles from read-only files through replaceable credential-provider, signer/verifier, OBO, and replay-detector interfaces.
- Give gateway, console, each owner, metrics collector, scheduler, migration job, and each worker queue a distinct environment-scoped identity/key. Never share private keys or accept migration identity for runtime traffic.
- Independently validate direct service JWT and OBO. Enforce service permission AND caller allowlist AND human permission AND assurance freshness AND RLS.
- Store bounded Redis replay markers until expiry for every OBO and privileged/mutation/governance/bulk/destructive/export service call, with documented fail-closed behavior.
- Split workers into source fetch, event parser, incident parser, watch monitor, enrichment, email intelligence, governance, CRM export, sequencing, meeting sync, and scheduler identities/queues.
- Sign task headers over task name, canonical argument digest, audience, correlation/causation, expiry, and `jti`; reject unsigned, altered, replayed, expired, wrong-audience, and unauthorized tasks before business/database access.
- Test wrong issuer/subject/audience/key/purpose, key overlap/removal, browser/user tokens at owners, modified/replayed OBO, caller-operation mismatch, unsigned tasks, and credential absence from logs.

#### Audit, database roles, and staged RLS

- Persist append-only audit from verified identity for privileged successes/denials, auth/session/security events, and service-auth failures, including operation, permission, resource, assurance, policy versions, environment, correlation/request IDs, bounded network metadata, and integrity HMAC.
- Add deterministic redaction and denial-flood aggregation. Fail privileged mutations with 503 if audit persistence fails; emit only redacted emergency security logs.
- Provision separate schema owner, migration, gateway security store, owner runtime, per-worker, reporting, session, audit writer/reader, retention, and test roles. Runtime roles are never table owners, superusers, or `BYPASSRLS`.
- Complete the 37-table classification. Initially exclude only `cyber_events` and `organization_email_patterns`, with strict grants, sensitive-column review, operation tests, and CI schema-change triggers.
- Add indexed classification, verified owner/assignee, owning workload, and policy-version scope fields only where required. Preserve display names but backfill ambiguous legacy ownership as restricted/unassigned.
- Define separate SELECT/INSERT/UPDATE/DELETE policies using `USING` and `WITH CHECK`, including reassignment/reclassification, governance state, foreign-key scope, reports/exports, bulk paths, workers, and pooled connection cleanup.
- Stage migrations for scope/backfill, roles/grants, disabled policies, shadow validation, grouped `ENABLE ROW LEVEL SECURITY`, then grouped `FORCE ROW LEVEL SECURITY`.
- Do not force a table until production-shaped tests cover missing context, allowed/denied CRUD, transitions, rollback/exception cleanup, connection reuse, worker isolation, reporting/export, and query-plan/latency evidence.
- Never use security-definer bypass, allow-all policies, superuser rollback, `BYPASSRLS`, or caller-supplied database context.
- Install verified transaction-local security context before every protected repository operation; deny absent context and prove rollback, exception, cancellation, and pooled-connection reuse cannot retain identity.
- Complete migration `0015` downgrade/roll-forward behavior and test it with schema-owner and non-owner runtime roles; the runtime connection used by any service or worker may not own protected tables.

#### CSRF, perimeter, deployment, and acceptance

- Enforce session-bound CSRF on every browser unsafe method; Dash obtains it from `/auth/session` and attaches it only to same-origin unsafe requests.
- Add Redis distributed limits for auth, callbacks, sessions, step-up, reads, mutations, bulk/export, and owner calls. Rate-limit denials before persistent audit and define fail-closed classes.
- Enforce exact/no CORS origins, trusted ingress CIDRs, TLS-only production ingress, JSON-only unsafe APIs, header/query/cookie/body/bulk bounds, authenticated `no-store`, HSTS/no-sniff/frame denial, and nonce/hash Dash CSP without `unsafe-eval`.
- Count streamed and chunked request bytes independently of `Content-Length`; reject missing, conflicting, malformed, compressed-over-limit, or overrun bodies and stop downstream processing at the declared operation limit.
- Apply route-class limits before expensive database/provider work and test replica-coordinated abuse, unavailable Redis behavior, bulk amplification, slow bodies, and retry storms.
- Keep minimal unauthenticated liveness; expose readiness only inside the cluster. Disable docs/OpenAPI/Redoc by default; require administrator step-up when enabled and metrics-collector identity for metrics.
- Update Helm for gateway-only TLS ingress, NetworkPolicies, distinct service accounts, per-workload key/trust mounts, distinct database credentials, Redis ACL/namespaces, and strict positive/negative rendering.
- Add a guarded deterministic local OIDC provider that cannot render/start in staging or production.
- Add complete unit, operation-contract, PostgreSQL/Redis, service-boundary, worker, browser, Helm, static/security, migration, and RLS-performance tests.
- Make Ruff, Bandit, full MyPy, tests, migration checks, Helm negative rendering, route/operation coverage, and security evidence mandatory. Resolve the OIDC hash-algorithm typing failure without weakening validation or adding a security-file exclusion.
- Run bounded Auth0 email-OTP and phishing-resistant step-up staging validation. Report live state only as passed, failed with redacted evidence, or blocked by missing environment access.
- Roll out by provisioning schema/roles/keys, deploying compatible service-auth topology with shadow RLS, enabling/forcing tested table groups, canarying Auth0 users, exposing gateway only, then revoking static credentials and removing legacy identity behavior.
- Roll back only to Sprint-25-compatible images or roll forward. Never restore caller-asserted identity, disable audit/RLS, add allow-all policies, or grant bypass roles.
- Acceptance requires zero unapproved legacy identity/static-token/demo-role references, complete generated matrices, deterministic/live/deployment evidence, refreshed graphify output, full documentation, and a criterion-to-evidence report.
- E1 cannot pass until anonymous requests are limited to minimal liveness and intentional authentication entry points, every protected operation denies missing/forged/stale identity, privileged audit failure blocks the mutation, owner services reject direct browser/user tokens, and Sprint 25c tenant context is enforced end to end.

#### Documentation requirements

- Update root README, architecture, dashboard/pipeline specifications, operations/incident runbooks, affected service/worker READMEs and technical READMEs, Helm/secrets guide, local/staging guides, testing strategy, API/service authentication, key rotation, database/RLS, permission/RLS matrices, audit/retention, bootstrap/recovery, Auth0 validation, and metrics/docs policy.
- Add an ADR for generic OIDC/Auth0 reference, email-OTP assurance limits, sessions/step-up, additive RBAC, gateway/owner trust, Ed25519/OBO, signed tasks, risk-based RLS, database roles/context, audit behavior, deterministic local-provider isolation, recovery, rejected alternatives, and future SPIFFE migration.
- Preserve the authoritative [Sprint 25 research input](SPRINT_25.md) and distinguish [Sprint 25a foundation evidence](docs/reports/sprint-25a-security-foundation.md) from future Sprint 25b production-completion evidence.

#### Sprint 25b closure checklist required before Sprint 25c implementation

This is a narrow closure pass, not a new feature sprint. Complete all six items below before adding tenant identifiers, tenant memberships, tenant-aware foreign keys, tenant RLS, placement, or support-access behavior in Sprint 25c. The purpose is to ensure that Sprint 25c extends proven identity, authorization, audit, database-role, and release-evidence foundations instead of hiding Sprint 25b gaps behind tenant predicates. Preparation and design work for Sprint 25c may proceed in parallel, but its schema and runtime implementation must not begin until this checklist is satisfied and the evidence report is corrected.

1. **Replace broad RLS grants and context-only policies with workload- and role-constrained least privilege.**
   - Replace any migration or role map that grants every writer `SELECT, INSERT, UPDATE, DELETE` on every protected table. Define an explicit table-by-operation grant matrix for gateway security storage, each owner service, reporting, session, audit writer/reader, retention, every worker queue, scheduler, migration, and test identities.
   - Ensure each deployment `LOGIN` role inherits exactly one intended `NOLOGIN` group role and is not a table owner, superuser, `CREATEDB`, `CREATEROLE`, or `BYPASSRLS`. Reject shared runtime database credentials and membership in multiple runtime groups during preflight or deployment validation.
   - Constrain every protected-table CRUD policy by all applicable dimensions: `context_valid`, exact database role or approved role group, exact verified `calling_workload`, required human or service permission, operation identifier, classification, owner/assignee/owning-workload scope, and allowed state transition. A merely non-empty permissions or workload setting must never authorize access.
   - Preserve separate `USING` and `WITH CHECK` expressions. Add negative tests for reclassification, reassignment, cross-owner foreign keys, worker queue theft, report/export overreach, audit mutation, and use of another service's valid context.
   - Exercise policies through real non-owner login roles against PostgreSQL. Prove missing, malformed, stale, wrong-role, wrong-workload, wrong-operation, and excessive-permission contexts deny all applicable CRUD. Prove rollback, exception, cancellation, and pooled-connection reuse clear transaction-local context.
   - Do not retain `FORCE ROW LEVEL SECURITY` merely because a smoke test passes. Rehearse shadow comparison, grouped enablement, forced policies, downgrade in a disposable pre-production database, and roll-forward. Record table counts, role attributes, grants, policy expressions, representative query plans, and allowed/denied CRUD evidence in the Sprint 25b report and generated RLS matrix.
   - **Exit evidence:** checked least-privilege grant/RLS matrices, PostgreSQL integration tests using the actual runtime roles, no shared owner-capable DSN, and zero policy that authorizes solely from non-empty context values.

2. **Finish the authoritative session, rotation, revocation, and provider-claim lifecycle.**
   - Keep PostgreSQL authoritative. If Redis caches session or principal state, use opaque/digested keys, cap cache staleness at 60 seconds, treat cached data as subordinate, and invalidate all relevant entries on local revocation, subject-wide logout, disablement, role/mapping/policy changes, step-up, tenant-independent security changes, and session rotation.
   - Atomically rotate the session identifier and CSRF binding every 15 minutes and after login, phishing-resistant step-up, provider-claim refresh, privilege change, mapping/policy version change, and suspected compromise. Concurrent use of the old identifier must not create two valid successors; the old cookie must fail immediately after committed rotation.
   - Enforce standard and remembered idle/absolute limits on every authoritative resolution. Prove idle extension never exceeds the absolute limit and expired, revoked, disabled, mapping-stale, or policy-stale sessions cannot be revived by Redis, concurrent requests, or pooled connections.
   - Refresh provider role claims at most every five minutes through a separately state/nonce/PKCE/browser-bound OIDC transaction. Until a successful authoritative refresh, stale or failed claims must reduce the session to session/profile self-service permissions; they must not retain ordinary, governance, export, or administrator permissions.
   - Re-evaluate the intersection of provider roles, local active bindings, role ceiling, principal status, assurance, and policy/mapping versions on every authoritative resolution or within the declared maximum cache bound. Unknown provider roles remain non-authorizing.
   - Add deterministic tests for concurrent rotation, periodic rotation, cache hit/miss, cache invalidation, Redis loss, stale provider claims, failed silent refresh, interactive recovery, logout-all, other-session revocation, disablement, and policy/role changes. Add a real PostgreSQL/Redis multi-process or multi-replica integration test rather than relying only on in-memory fakes.
   - **Exit evidence:** session lifecycle diagram and runbook, passing PostgreSQL/Redis lifecycle tests, explicit cache keys/TTLs/invalidation inventory, and browser evidence that an old session/CSRF pair cannot survive rotation or revocation.

3. **Make privileged auditing transactionally mandatory and denial auditing bounded.**
   - Create privileged success audit records from verified operation context in the same database transaction as security administration, governance decisions/overrides, sensitive export, destructive work, bootstrap/emergency changes, and other-user session revocation. If audit construction, redaction, integrity HMAC, or persistence fails, roll back the business mutation and return a uniform redacted `503`.
   - Audit authentication/session/security events and privileged denials with verified human/service/OBO identity, permission, operation/resource, assurance and authentication age, mapping/policy versions, environment, request/correlation identifiers, bounded network metadata, decision/denial category, and integrity HMAC. Never accept actor, tenant, permission, decision, or resource scope from caller-controlled audit fields.
   - Enforce append-only database behavior for runtime roles: audit writers may insert but cannot update/delete; readers cannot write; ordinary owners/workers cannot directly write arbitrary audit rows. Test attempted update, delete, HMAC omission/tampering, role misuse, and audit-table access without verified context.
   - Aggregate unauthenticated and rate-limit denial floods in Redis with bounded cardinality and expiry. Persist only policy-defined summaries so an attacker cannot exhaust the audit store. Security dependency failures must emit only redacted emergency logs without credentials, cookies, authorization codes, tokens, raw claims, email contents, provider payloads, or exception details.
   - Add fault-injection tests that fail audit serialization, redaction, HMAC, insert, commit, and database availability. Prove every protected mutation rolls back, no side effect/outbox/task/provider call escapes, the response is redacted, and a subsequent healthy transaction is unaffected.
   - **Exit evidence:** operation-to-audit matrix, database grant/policy evidence, append-only and failure-injection integration tests, denial aggregation tests, and a criterion demonstrating zero privileged mutation can commit without its matching audit event.

4. **Complete first-administrator bootstrap and emergency-grant consumption workflows.**
   - Implement the privileged CLI or migration-job command that atomically consumes the SHA-256-digested, Redis-backed, one-time 60-second bootstrap proof. Producing a proof through HTTP is insufficient. Consumption must run under the narrowly scoped migration/bootstrap credential, bind issuer, subject, purpose, environment, session, assurance, authentication time, request/correlation identifiers, and reject replay, expiry, wrong environment/purpose/session/subject, or an untrusted caller.
   - First-administrator creation must succeed only when no active administrator exists, under a database lock or serializable invariant preventing concurrent double bootstrap. Require a non-empty reason and separate approver evidence, create the minimum administrator binding, invalidate affected session/principal caches, rotate policy/mapping versions as applicable, and commit the immutable audit event in the same transaction.
   - Implement emergency-grant creation, activation, status, revocation, and expiry persistence rather than proof generation alone. Require a target different from the approver, phishing-resistant assurance no older than 15 minutes, a reason, incident/ticket reference, separate approver evidence, explicit permissions, and an expiry no longer than one hour.
   - Maintain a hard denylist for service permissions, database roles, table ownership, superuser, `BYPASSRLS`, migration capability, audit alteration, and policy/RLS disablement. Emergency permissions remain subject to ordinary operation authorization, owner-service authentication, OBO, CSRF, rate limits, RLS, and audit.
   - Add deterministic and PostgreSQL/Redis tests for proof replay/races, two concurrent first-admin attempts, existing-admin denial, missing/identical approver denial, excessive scope/expiry denial, cache invalidation, automatic expiry, explicit revocation, audit failure rollback, and recovery after a failed attempt. Ensure secrets/proofs are redacted from command output and logs.
   - Publish operator commands, credential boundaries, approval format, lost-access recovery, incident handling, expiry/revocation checks, and evidence-retention rules. The runbook must describe only implemented commands and must not imply a non-existent CLI.
   - **Exit evidence:** executable CLI help and integration transcript with secrets redacted, one-time/race tests, first-admin invariant evidence, bounded emergency-grant tests, and transactionally paired audit records.

5. **Run and retain the mandatory image vulnerability scan and SBOM gates.**
   - Build one release-shaped image from the reviewed commit and capture its immutable OCI digest. Run Trivy against that digest with scanner/database errors treated as failures and with `HIGH` and `CRITICAL` findings failing unless a time-bounded, owned, documented exception is approved. Do not use mutable tags, `--ignore-unfixed`, severity downgrades, or broad ignore files merely to make the gate pass.
   - Generate both SPDX JSON and CycloneDX JSON SBOMs with Syft from the exact same image digest. Validate that both artifacts are parseable, non-empty, identify the image/package contents, and record the source commit, image digest, scanner/generator versions, invocation, timestamp, and artifact checksums.
   - Prefer a protected CI job with pinned scanner/generator versions or immutable action/container digests. Authenticate to the registry without exposing credentials; retain the Trivy report and both SBOMs as release artifacts; prevent an untrusted pull request from replacing, suppressing, or approving its own scan evidence.
   - Triage every failing vulnerability to remediation, image/dependency upgrade, or a narrowly scoped exception containing CVE, affected package/image, exploitability rationale, compensating controls, owner, approval, creation date, and expiry. Expired exceptions fail the gate. Re-run the scan after remediation and preserve both the failing and passing reports where policy requires.
   - Link the passing report and SBOM checksums to the same promoted image digest used by Helm. A scan of `ghostrecon:local`, a source directory, a different architecture, or an earlier build is diagnostic only and does not satisfy release evidence.
   - **Exit evidence:** passing `make image-scan` and `make sbom` or equivalent protected CI jobs, `trivy-report.json`, `sbom.spdx.json`, `sbom.cyclonedx.json`, tool versions, checksums, exact image digest/commit linkage, and approved unexpired exceptions if any.

6. **Reconcile the plan, evidence, generated matrices, and completion status before handoff.**
   - Update `sprints/CURRENT_PLAN.md` so it no longer describes the pre-implementation baseline. Either close it as a truthful Sprint 25b completion record or replace it with a Sprint 25c plan only after items 1-5 pass. Preserve unresolved external and release gates explicitly; do not convert `blocked`, `not run`, or partial deterministic coverage into `passed`.
   - Revise `docs/reports/sprint-25b-production-security.md` criterion by criterion. Cite exact tests, commands, artifact paths/checksums, database roles and policy counts, image digest, CI run, and dated environment. Separate deterministic, local integration, staging, and production-shaped evidence.
   - Regenerate and check operation, RLS/grant, workload/caller, task/queue, audit, session/cache, credential-projection, and system-endpoint matrices. CI must reject stale matrices, broad/shared credentials, missing operations/tables/tasks/CLI actions, and differences between documented and rendered topology.
   - Run final searches for legacy identity/static-token/demo-role paths, raw actor/role defaults, shared database credentials, missing Redis ACL namespaces, direct owner ingress, unauthenticated readiness/metrics/docs, unclassified operations/tables/tasks/CLI commands, permissive RLS expressions, and documentation that describes unimplemented security behavior. Every remaining match must be a negative test, historical record, or explicitly approved exception.
   - Re-run the complete deterministic and integration suite: Ruff, Bandit, full MyPy, full tests including browser/service/worker/PostgreSQL/Redis cases, migration upgrade/downgrade/roll-forward, Helm positive and negative renders, Compose validation, generated-matrix checks, image scan, SBOM, and `git diff --check`. Refresh `graphify` after the final code/document changes.
   - Auth0 email-OTP and phishing-resistant step-up evidence may remain `blocked_missing_environment_access` only when tenant credentials, mailbox, or authenticator access are genuinely unavailable, as already allowed by Sprint 25b. Record the missing access precisely and retain the staging procedure. A failed flow, known interoperability defect, missing principal bootstrap path, or available-but-unconfigured environment is not equivalent to missing access and must be fixed or recorded as failed before handoff.
   - Amend the Sprint 25b completion claim only when items 1-5 and all locally runnable mandatory gates pass. State explicitly that Sprint 25c implementation may begin, while E1, live-provider use, real personal data, shared SaaS, and production promotion remain blocked until their later tenant-isolation and enterprise gates pass.
   - **Exit evidence:** a reviewed closure table mapping every checklist bullet to evidence or an explicitly permitted external block, current generated matrices, a clean mandatory-gate run, refreshed graph output, and an approved Sprint 25c start decision.

### Sprint 25c - Shared SaaS Tenant Isolation and Privileged Support Access

#### Objective and production outcome

Make each enterprise an isolated tenant and make the active tenant a server-verified part of every human, service, worker, data, cache, queue, provider, export, analytics, and AI execution context. The default production topology uses a shared schema with mandatory tenant keys and forced PostgreSQL RLS; customers with contractual, regulatory, residency, or enhanced-isolation requirements can receive a dedicated database through the same logical authorization and evidence model. Platform operators have no ambient customer-data access.

#### Current implementation and explicit gaps

- `IdentityContext.workspace_id` defaults to `default`, CRM export has an optional provider workspace field, and the security principal/session/role-binding tables are not tenant-scoped.
- Domain tables, unique constraints, foreign keys, repositories, reports, caches, queues, outbox records, provider credentials, exports, and audit records do not yet enforce an enterprise tenant boundary.
- Multi-workspace/multi-tenant authorization and cross-workspace access were explicit Sprint 25 non-goals; shared SaaS is therefore prohibited until this sprint passes.
- There is no separate platform-operator identity plane, tenant-bound support grant, tenant switch protocol, dedicated placement model, or negative cross-tenant test suite.
- Requires Sprint 25b identity, service trust, operation authorization, database roles/context, replay protection, and gateway-only topology. Every later production sprint requires Sprint 25c.

#### Tenant, membership, role, and session contracts

- Add immutable opaque `Tenant` identifiers, tenant status, display metadata, policy references, created/disabled timestamps, and isolation mode. Slugs, domains, provider workspaces, IdP organization claims, and client-supplied values never become authorization identifiers.
- Add `TenantMembership` with tenant, principal, status, tenant-scoped roles/permissions, grantor, reason, policy/mapping versions, created/updated/disabled timestamps, and optional expiry. Enforce one active membership row per tenant/principal and audit every transition.
- Define additive tenant roles `enterprise_member`, `enterprise_manager`, and `enterprise_administrator`. A principal may hold different roles in explicitly granted tenants; normal users have one tenant by default and never gain another membership through discovery, email domain, provider claims, or platform employment.
- Add `GET /auth/tenants` to list only the authenticated principal's explicit active memberships and permitted tenant-switch targets.
- Add `POST /auth/tenant/switch` accepting a target tenant only as a requested transition. Revalidate membership, tenant status, assurance, and policy server-side; revoke the old session; create a new tenant-bound session and CSRF secret; rotate every OBO/service/task capability; and audit source tenant, destination tenant, reason, session IDs, and outcome.
- Bind every ordinary session to exactly one active tenant and membership version. Revalidate membership during login, switch, rotation, privilege change, and with no more than 60 seconds of cache staleness; high-risk operations revalidate synchronously.
- Derive active tenant from the verified session or signed service/OBO/task context. Reject `X-Tenant`, query/body tenant selectors on ordinary domain operations, mismatched resource tenants, stale membership versions, and tokens created for another tenant.
- IdP organization claims may propose login mapping only. A local active membership and tenant policy remain authoritative; ambiguous or unknown mappings deny access and enter an audited provisioning/review flow.

#### Database, placement, and migration requirements

- Add non-null indexed `tenant_id` to every tenant-owned security, identity, source, raw item, event, incident, account, contact, email, score, review, governance, audit, outbox, CRM, sequence, mail, meeting, policy, and operational record.
- Inventory every table as tenant-owned, platform-control, global-reference, or prohibited. CI rejects unclassified tables, schema changes without tenant policy, and tenant-owned relationships without tenant-safe keys.
- Use composite tenant-aware unique constraints and foreign keys where records relate across tables so inserts, updates, reassignment, bulk operations, and cascades cannot form cross-tenant relationships even if application checks fail.
- Extend transaction-local PostgreSQL context with tenant, actor type, membership/support grant, operation, and policy versions. Missing, malformed, stale, or mismatched context denies before repository access.
- Define separate forced SELECT/INSERT/UPDATE/DELETE RLS policies with `USING` and `WITH CHECK` for every tenant-owned table. Runtime, reporting, worker, retention, migration, support, and platform roles are never table owners, superusers, or `BYPASSRLS`.
- Default to shared-schema forced RLS. Add server-controlled `TenantPlacement` for shared pool or dedicated database, region/residency, storage/index namespaces, key references, migration version, health, and move state. Clients and ordinary tokens cannot select or override placement.
- Keep tenant keys and forced RLS in dedicated databases as defense in depth. Apply identical logical schema, migrations, backup/restore, audit, and negative isolation tests to shared and dedicated placements.
- Migrate in stages: create platform and deterministic local/demo tenants; add nullable tenant keys; backfill only provable ownership; quarantine ambiguous records; add tenant-aware keys/indexes; shadow-check repositories; make keys non-null; enable then force RLS; revoke legacy grants and default-workspace behavior.
- Provide a restartable, audited placement-move workflow with source freeze/checkpoint, copy and validation, cutover, rollback window, old-copy retention/deletion policy, and proof that no request, event, or provider action crosses placement during migration.

#### Non-database isolation requirements

- Namespace Redis sessions, caches, replay markers, locks, quotas, schedules, and idempotency keys by immutable tenant ID. Prevent key construction from unverified request input and test collisions/eviction across tenants.
- Include tenant, placement version, operation, audience, canonical argument digest, correlation/causation, expiry, and `jti` in signed outbox, queue, scheduler, worker, and AI job envelopes. Reject missing/altered tenant context before database, cache, search, object, model, or provider access.
- Scope search and vector indexes, retrieval filters, object-storage prefixes/buckets, exports, temporary files, analytics datasets, feature stores, model context, prompts, tool calls, and results to one tenant. Future stores or AI features cannot ship until their isolation adapter and negative tests are registered.
- Never batch raw records from different tenants into one provider request, AI execution context, export, file, trace, or support operation. Platform-wide telemetry may use only explicitly approved de-identified aggregates through a separate non-support pathway.
- Store CRM, mail, calendar, search, verifier, webhook, signing, and other provider configuration/credentials per tenant and placement. Resolve inbound webhook tenant from authenticated provider configuration and workspace identity, never from a caller header or payload alone.
- Apply tenant-specific quotas, rate limits, retention, suppression, legal basis, source permissions, integration enablement, data residency, encryption-key references, and egress policy at the final service boundary as well as the gateway.
- Propagate tenant audit context through HTTP, OBO, tasks, database, cache, provider, export, support, and AI boundaries without using tenant IDs or customer identifiers as unbounded metric labels.

#### Platform administration, support, and emergency access

- Use a separate platform issuer/audience, roles, sessions, keys, routes, and operation policies for SaaS maintenance. Platform identities receive no tenant membership, tenant-data permission, search/export capability, or RLS bypass by default.
- Add `SupportAccessGrant` with platform principal, one tenant, support case/ticket, reason, requested permissions, tenant approval evidence/policy, approvers, start, expiry, revocation, assurance, session, status, and immutable audit references.
- Add platform-only request/approve/activate/status/revoke support operations. Activation requires phishing-resistant step-up and creates a separate delegated support session that identifies the platform actor and tenant; it never impersonates a customer principal.
- Default a support grant to one hour and cap it at four hours. Write, export, integration, automation, security, policy, or destructive scopes require explicit tenant approval; tenant policy may pre-authorize narrowly defined read-only diagnostics.
- Bind support access to one tenant and the minimum operation set. It cannot switch tenants, create memberships, search/compare/aggregate/export across tenants, use ordinary platform sessions for tenant data, or continue after grant/session/tenant expiry, revocation, disablement, or policy change.
- Record actor identity/type, active tenant, ticket/reason, approval, start/expiry, records viewed/modified, exports/downloads, automation/integration/administrative actions, denials, session creation/termination, and every privilege change in tamper-evident audit.
- Add a separately controlled break-glass path only for critical incidents when ordinary tenant approval is unavailable. Require separate credentials, two distinct security approvers, phishing-resistant authentication, an incident reference, explicit scopes, a maximum 60-minute expiry, immediate high-severity alerts, immutable audit, post-incident review, and customer notification within 24 hours after closure.
- Break-glass is not a global superuser: it creates one tenant-bound delegated session, cannot disable/alter RLS, cannot browse other tenants, and must be exited before another tenant can be accessed.

#### Safety, tests, rollout, and acceptance

- Generate tenant table, relationship, operation, store, queue, provider, export, analytics, support, and placement matrices. CI fails for missing ownership, context propagation, policy, test, or evidence.
- Prove tenant A cannot list, read, infer existence, mutate, relate, search, retrieve, cache-collide, enqueue, export, reconcile, administer, or supply AI context for tenant B through APIs, direct owner calls, repositories, bulk paths, foreign keys, pooled connections, retries, dead letters, reports, or provider callbacks.
- Prove changing a client-supplied tenant/header/query/body value cannot change authorization; tenant switching invalidates the old session/CSRF/OBO/task chain; disabled/expired membership fails within the declared bound; ambiguous legacy rows remain inaccessible.
- Prove platform administrators have no tenant-data access without an active grant; support access is one-tenant and scope-bound; unapproved/expired/revoked access fails immediately; support cannot switch/export/aggregate; break-glass generates required approvals, alerts, expiry, audit, review, and notification evidence.
- Run the same CRUD, relationship, report, export, job, cache, provider, backup/restore, failover, and penetration tests against shared-schema and dedicated-database placements.
- Roll out one isolated test tenant at a time, then multiple adversarial tenants, then dedicated placement. Never enable an allow-all compatibility policy, default tenant fallback, platform bypass role, or caller-selected placement during rollout or rollback.
- Acceptance: every request and asynchronous action has exactly one verified tenant; every tenant-owned record and non-database artifact is isolated; all RLS is forced under non-owner roles; support is explicit and temporary; no permanent global tenant-data superuser exists; and E1 tenant-isolation evidence is signed.

#### Documentation requirements

- Publish the tenant and placement model, membership/role/session contracts, tenant switch protocol, trust boundaries, RLS/table/store matrices, support and break-glass flows, migration/rollback, dedicated-database/residency operations, provider isolation, AI/data-use constraints, audit fields, incident response, and residual risks.
- Update architecture, security ADRs, permission/RLS matrices, API/service/task authentication, Helm/secrets, operations/runbook, testing strategy, privacy/retention, provider, export, analytics, AI, and every affected service/worker document.

### Sprint 26 - Source Operations Control Plane and Durable Source Scheduling

#### Objective and production outcome

Make the persisted source registry an operable control plane and continuously schedule eligible event/incident sources without manual task or database intervention.

#### Current implementation and dependencies

- SourceDefinition in src/ghostrecon/models/db/sources.py stores adapter, polling/rate policy, checkpoint, freshness, retry budget, policy, and operating state; contracts begin in src/ghostrecon/models/api/source_contracts.py.
- source_registry.py, source_adapters.py, workers.py, and worker_runtime.py can fetch/parse one source, but beat schedules watch monitoring rather than every due source. Reporting/console health is read-only while the runbook describes unsupported pause/replay/acknowledge actions.
- Requires Sprint 24 profiles, Sprints 25b-25c identity/tenant isolation, and the E1 outbound-provider gate. Preserve checkpoints/policy; Sprint 27 consumes lifecycle events but is not needed for scheduling.

#### Implementation and interface requirements

- Add governance-controlled list, inspect, create, update, enable, pause, resume, test, run-now, acknowledge-error, and bounded-replay APIs plus matching console controls.
- Require optimistic versions and idempotency keys on mutations; replay/policy changes require confirmation, reason, and audit.
- Query persisted due enabled sources by interval/next-run state. Use distributed finite leases so one source/checkpoint has at most one active fetch.
- Enforce per-source concurrency, request rate, retry budget, exponential backoff/jitter, timeouts, size/crawl bounds, and failure isolation.
- Before any request, require the source to be enabled, operationally eligible, tenant-authorized, and permitted by an authoritative effective policy; test/run-now/replay cannot bypass this decision.
- Centralize outbound URL validation for source/search/crawl clients: allow only configured schemes/ports/registrable domains; resolve and reject loopback, private, link-local, multicast, reserved, and cloud-metadata targets; re-resolve and reauthorize every redirect; defend against DNS rebinding and mixed public/private answers.
- Stream responses under compressed and decompressed byte limits; bound redirects, DNS answers, headers, JSON/XML nesting/items, parser work, and total wall time; validate content type/encoding before parsing and discard/quarantine over-limit bodies without persisting raw provider errors.
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
- E1 source enablement additionally requires negative tests for prohibited source state, every private/reserved address family, redirect-to-private, rebinding, oversized/chunked/compressed responses, unexpected content, timeout, quota exhaustion, and redacted exceptions.

#### Documentation requirements

- Update affected architecture, pipeline/dashboard specs, runbook, root README, ingestion/event/incident/reporting/console/gateway/governance docs, and Helm docs if scheduler/queue/topology changes.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 27 - Transactional Outbox Dispatch and Automated Pipeline Orchestration

#### Objective and production outcome

Turn persisted outbox intent and task islands into a reliable, observable, idempotent pipeline that advances real records automatically until an explicit human or policy gate.

#### Current implementation and dependencies

- Workflows write OutboxEvent rows, primarily modeled in src/ghostrecon/models/db/governance.py, but no dispatcher claims/publishes them. Persistence mainly exposes published_at, without full lease/retry/dead-letter state.
- src/ghostrecon/workers.py and worker_runtime.py expose ingestion, parsing, enrichment, scoring, governance, CRM, sequencing, and meeting tasks as callable islands; due sequence and inbound-mail work is unscheduled.
- Requires Sprints 24-26, Sprint 25b service identities, and Sprint 25c tenant isolation. Existing approval boundaries remain authoritative.

#### Implementation and interface requirements

- Add available time, lease owner/expiry, attempt, last error, published time, terminal status, and dead-letter/replay metadata plus indexed bounded due claims.
- Claim batches transactionally with concurrent-safe database locking and finite recoverable leases. Publish to explicit queues and mark delivery only after broker acceptance.
- Add capped backoff/jitter, poison isolation, dead-letter inspection/metrics, authorized replay, and immutable original lineage.
- Implement versioned idempotent consumers for source ingestion, event/incident parsing, resolution, scoring, review creation, CRM, sequences, inbound mail, and meetings.
- Encode the automatic-versus-analyst/governance/CRM/outreach/meeting transition table. Never infer export, enrollment, or sending from upstream approval.
- Propagate request/correlation, causation, schema, source-definition/run/item, and outbox IDs through rows, messages, tasks, and logs.
- Persist tenant and placement version on outbox/inbox rows and sign tenant, operation, audience, canonical argument digest, correlation/causation, expiry, and `jti` in every broker/task envelope. Reject absent, altered, replayed, expired, wrong-tenant, or wrong-placement context before business or data access.
- Namespace idempotency, leases, routing keys, dead letters, result metadata, quotas, and replay authorization by tenant. Never store sensitive task results in Redis by default; define bounded result retention and minimize payloads.
- Reauthorize current tenant membership/support grant, policy, resource, and provider eligibility when a delayed/replayed consumer performs a side effect; producer-time authorization alone is insufficient.
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
- Prove a tenant cannot observe, claim, replay, dead-letter, route, or consume another tenant's work and that an unsigned or tenant-mismatched job creates no database, cache, provider, audit-success, or AI side effect.

#### Documentation requirements

- Update affected architecture, pipeline spec, runbook, producer/consumer docs, event/queue technical docs, and Helm topology/configuration.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 28 - Live Cybersecurity Event and Participant Acquisition

#### Objective and production outcome

Acquire useful real cybersecurity events and permitted participant evidence from official sources through one bounded, lineage-complete scheduled/manual pipeline.

#### Current implementation and dependencies

- Seeded DEF CON, Black Hat, BSides, OWASP, and FIRST sources use generic http_page extraction, retaining mostly title/description and producing unknown dates, timezone, venue, or format.
- Participant extraction in src/ghostrecon/services/event_intelligence/ works mainly for Schema.org data. NOTES.txt requests scraping a manually supplied event URL.
- Requires Sprints 24 and 26-27 for safe live configuration, scheduling, and orchestration, plus Sprints 25b-25c identity, governance, and tenant isolation. Live canaries require the applicable E1 source/provider gate.

#### Implementation and interface requirements

- Add source-specific extraction using Schema.org, ICS, RSS, bounded HTML traversal, and source-owned selectors only where structured formats are absent.
- Extract canonical name/URL, local dates/timezone and UTC instants, venue/structured address, format/virtual URL, topics, organizers, speakers, sponsors, and permitted public profiles.
- Manual URL submission must enqueue the same fetch/parse workflow and preserve manual actor, submitted URL, source run/item, parser version, and correlation lineage.
- Discover detail/participant pages only within allowlisted domains, depth/page/size/time budgets, robots/terms policy, and configured reuse permission.
- Apply Sprint 26 outbound validation to every discovered URL, DNS resolution, redirect hop, asset/API request, geocoder call, and parser fetch. A public starting URL never authorizes a private or different-domain redirect.
- Scope source definitions, manual submissions, fetch leases, caches, raw items, parser diagnostics, participant evidence, and geocoder results to the active tenant; deduplication may not merge or reveal records across tenants.
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
- Bounded staging canaries fetch official sites without asserting presentation text and run only after E1, in an isolated tenant, with authoritative source policy, fixed budgets, recorded egress, retention, and cleanup.
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
- Requires Sprints 24, 26, and 27; uses Sprints 25b-25c identity/tenant isolation and Sprint 28's source/parser operational patterns. Live canaries require the applicable E1 provider gate.

#### Implementation and interface requirements

- Schedule GDELT, CISA advisories/RSS, trusted RSS, CISA KEV, NVD, and SerpAPI watch queries through the registry with durable checkpoints, quotas, deduplication, and evidence retention.
- Apply Sprint 26 outbound/response controls to configured provider endpoints and every returned/followed URL. Keep API keys out of query/error/audit telemetry and resolve provider configuration, quota, cache, checkpoint, and watch scope per tenant.
- Prevent cross-tenant watch aggregation, evidence deduplication, incident grouping, search results, reports, exports, and provider batches unless an explicitly approved de-identified platform aggregate contract applies.
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
- Add bounded staging canaries for each provider only after E1 and browser/contract tests for review, evidence, watch status, governance decisions, tenant separation, credential isolation, and redacted provider failures.
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
- Requires Sprints 24 and 27, consumes event/incident evidence from Sprints 28-29, and respects Sprints 25b-25c identity/tenant isolation plus Sprint 26 outbound policy and controls. Live enrichment requires the applicable E1 verifier/search/crawl gate.

#### Implementation and interface requirements

- Remove synthetic domain inference from all non-demo workflows. Use OpenSERP for official sites and permitted professional profiles, persisting query, rank, URL, snippet, provider, retrieval time, and lineage.
- Validate selected corporate domains through redirect chain, registrable-domain/public-suffix normalization, website identity signals, DNS evidence, and suspicious-domain checks.
- Persist crawler discoveries and feed canonical candidates; retain multiple plausible organizations/domains and route ambiguity to analyst review.
- Enforce allowlists, robots/terms policy, crawl budgets, prohibited sources, timeouts, and content-retention limits.
- Generate email candidates only from verified domains and person names with permitted lineage. Batch verifier calls with health, bounded concurrency/retries, and explicit valid/invalid/catch-all/ambiguous/unknown outcomes.
- Remove caller-provided `verification_results` from production contracts. Production verification outcomes must come from an authenticated configured verifier response bound to tenant, candidate, request/attempt, provider, and time; deterministic injected results are test/local-only and cannot render or start in strict profiles.
- Never allow `valid`, `deliverable`, or similar caller-authored fields to update canonical contact email/status, learn organization patterns, satisfy outreach eligibility, or emit verified events. Persist only bounded/redacted provider evidence with defined retention.
- Scope discovered domains, accounts, contacts, candidates, learned patterns, search/crawl/DNS evidence, verifier batches/results, caches, review queues, and any retrieval/AI context by tenant. A pattern learned in one tenant cannot score or verify another tenant's address.
- Learn organization email patterns only from verified evidence; a generated pattern match is never itself verification.
- Extend candidate/evidence contracts and persistence for observed versus generated origin, search/crawl/DNS/redirect lineage, alternatives, selection decision, verifier provider/attempt/outcome, and pattern evidence. Expose provider health and ambiguity through reporting/review UI.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Never present generated domains/profiles/emails as observed provider data, crawl denied sources, or classify pattern-only addresses as verified.
- Prove missing domains stay missing when discovery fails. Test suspicious/conflicting domains, redirects, public suffixes, outages, denied crawl, budgets, catch-all, verifier timeout/retry, and ambiguous alternatives.
- Test forged caller verification payloads, candidate/tenant mismatch, replayed/stale provider results, wrong verifier identity, oversized provider responses, raw-payload redaction/retention, and attempts to unlock outreach or pattern learning without authoritative verification.
- Add OpenSERP/verifier contract tests, database workflow tests, browser review tests, and bounded staging canaries with protected credentials.
- Acceptance: a real participant/watch target reaches review with complete search/crawl lineage; all candidate origins are explicit; absence and ambiguity remain honest; no caller or other tenant can manufacture a verified canonical email or policy-eligible contact.

#### Documentation requirements

- Update affected enrichment, email, event, incident, scoring, governance, reporting, console, gateway docs plus architecture, pipeline/dashboard specs, runbook, public-enrichment ADR, and root README.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 31 - Attio Provisioning, Export, Reconciliation, and Webhook Operations

#### Objective and production outcome

Operate Attio as the approved sales-record system with preflighted schema, idempotent export, authenticated webhooks, continuous reconciliation, and visible drift.

#### Current implementation and dependencies

- CrmClient implementations in src/ghostrecon/services/crm_attio.py and crm_exports/ support Attio export/search and idempotent batch planning, but assume objects, attributes, and lists exist.
- There is no continuous reconciliation or authenticated webhook intake; credentials can fail late without Sprint 24.
- Requires Sprints 24, 25b-25c, and 27; consumes tenant-scoped approved records from Sprint 30. CRM export remains distinct from outreach approval and live Attio work requires the E1 CRM gate.

#### Implementation and interface requirements

- Add read-only schema preflight for required objects, attributes, lists, permissions, workspace identity, and supported API capabilities.
- Add an explicitly invoked administrator-only provisioning/migration plan and apply operation only where supported; preview changes and require version/idempotency/confirmation/audit.
- Persist provider configuration version and workspace identity with batches/items.
- Store Attio credentials, workspace identity, schema/config version, lists, rate/circuit state, batches/items, idempotency, reconciliation, repair, and webhook keys per tenant. Resolve them from verified tenant context and never accept a client-selected workspace as authority.
- Bind every export batch to exactly one tenant and provider workspace; reject mixed-tenant selections before planning and reauthorize every item before provider write.
- Add signed webhook intake for supported record/list changes, verify timestamp/signature/workspace, retain provider event IDs, and prevent replay. Derive tenant from the authenticated webhook key/configuration plus verified provider workspace; payload/header tenant IDs cannot select the tenant.
- Schedule reconciliation for missing records, changed stable IDs, partial list membership, and meeting/outcome drift; make each discrepancy visible and repairable.
- Coordinate read/write rate limits across replicas, honor retry metadata, classify terminal/retryable failures, expose token health/rotation/circuit/degraded state.
- GhostRecon remains authority for intelligence lineage/approval; Attio remains authority for approved sales records. Export never grants outreach approval or sequence enrollment.
- Publish preflight/provision/reconcile/webhook contracts, webhook event/version rules, reconciliation state, provider workspace/config fields, and authorized repair APIs.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Provisioning is never automatic at startup; reject invalid signatures, stale/replayed events, and wrong workspaces. Never overwrite intelligence lineage from provider data.
- Contract tests cover preflight, provisioning plans, upserts/list entries, pagination/rates, webhook signature/replay/workspace, reconciliation, circuit, and rotation.
- Database/integration tests prove retries/reconciliation are idempotent; browser tests cover preflight, drift, repair, roles, and degradation.
- Use one isolated provider workspace per staging tenant for bounded live acceptance after E1; prove wrong-workspace, wrong-key, cross-tenant record IDs, mixed batches, webhook confusion, reconciliation drift, and support-session export are denied.
- Acceptance: repeats create no duplicate people/companies/custom objects/list entries; drift is visible/repairable without database edits; export cannot activate outreach.

#### Documentation requirements

- Update affected CRM, governance, reporting, console, sequencing-import, meeting, gateway docs plus architecture, pipeline/dashboard specs, runbook, Attio ADR, Helm secrets guide, and root README.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 32 - Production Sequencing, Mail Delivery, and Google Calendar Handoff

#### Objective and production outcome

Operate approved outreach and meeting handoff with at-most-once business outcomes, durable mailbox state, sender readiness, and reconciliation across SMTP/IMAP, Google Calendar, and Attio.

#### Current implementation and dependencies

- SMTP/IMAP adapters exist in src/ghostrecon/services/sequence_adapters.py; due-step and inbound-poll tasks exist but are not scheduled. IMAP relies on UNSEEN and simple sender/subject classification. SMTP STARTTLS and IMAP SSL currently omit an explicitly verifying TLS context; IMAP also lacks a connection timeout and message-byte limit.
- Google Calendar service-account support and a fake fallback live under src/ghostrecon/services/calendar_adapters/; sender-domain readiness, durable mailbox checkpoints, and provider reconciliation are incomplete.
- Requires Sprints 24, 25b-25c, 27, 30, and 31. Meeting booking, CRM export, and outreach approvals remain independent; live mail/calendar use requires the applicable E1 gate.

#### Implementation and interface requirements

- Run due-step and inbound-mail schedules through Sprint 27 orchestration, isolating sender, mailbox, sequence, and provider failures.
- Persist mailbox checkpoints and stable message/provider IDs independently of UNSEEN. Correlate replies/bounces with Message-ID, In-Reply-To, References, envelope/provider IDs, and stored outbound lineage.
- Add bounded retries, timeout/error classes, terminal delivery states, operator-visible recovery, and transactional/idempotent send claims.
- Build SMTP and IMAP with `ssl.create_default_context`, certificate-chain validation, hostname verification, current minimum TLS policy, and explicit timeouts. Strict profiles reject disabled SMTP TLS, insecure contexts, plaintext authentication, invalid certificates, hostname mismatch, and unsupported downgrade.
- Bound IMAP search/fetch counts, individual and cumulative message bytes, headers, MIME depth/parts, attachment handling, parsing work, and mailbox poll time. Do not persist or log raw bodies unless an explicit tenant retention policy requires a minimal protected artifact.
- Claim/lock delivery transactionally before SMTP, use stable message/provider idempotency identifiers where available, reconcile ambiguous outcomes, and make crashes before/after network send unable to produce an untracked or silently duplicated business outcome.
- Scope senders, mailboxes, credentials, templates, contacts, suppressions, quotas, messages, checkpoints, replies/bounces, calendar identities/events, retries, reconciliation, and operator controls to one tenant.
- Immediately before send, re-evaluate current verification, lawful basis, outreach approval, suppression, evidence freshness, sequence/sender limits, and unsubscribe requirements.
- Validate SPF, DKIM, DMARC, envelope sender, reply mailbox, unsubscribe configuration, and provider identity before enabling a sender.
- Reconcile Google Calendar create/update/cancel via stable meeting IDs; validate credentials and delegated access at meeting-service startup/readiness.
- Extend sender/mailbox/message/delivery/meeting contracts and persistence for readiness, checkpoints, provider IDs, correlation, attempts, terminal state, bounce/reply classification, suppression action, and reconciliation drift.
- Provide authorized retry/reconcile controls and reporting for delivery/mailbox/calendar health without exposing message bodies or credentials.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Never send without fresh approval/policy checks, use UNSEEN as the sole checkpoint, treat auto-replies as positive replies, or couple booking/export/outreach approval.
- SMTP/IMAP integration tests use isolated servers/sandboxes and cover valid/private CA chains, invalid/expired certificates, hostname mismatch, STARTTLS downgrade, plaintext configuration, duplicate/rescanned/oversized messages, delayed bounces, auto-replies, unsubscribe, suppression races, sender limits, timeouts, concurrent sends, ambiguous outcomes, and worker crashes.
- Google Calendar contract tests cover authentication, delegated access, booking, free/busy, update/cancel, rates, reconciliation, rotation, and outages. Add browser recovery/status tests.
- Acceptance: approved outbound email sends at most once; inbound state changes at most once across polls; booked meetings reconcile consistently across GhostRecon, Google Calendar, and Attio; transport identity is verified; and no mail/calendar record, credential, quota, or action crosses tenants.

#### Documentation requirements

- Update affected sequencing, email, meeting, CRM, governance, reporting, console, gateway docs plus architecture, pipeline/dashboard specs, runbook, Helm README/secrets guide, and root README.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 33 - End-to-End Observability, Data Quality, and Incident Response

#### Objective and production outcome

Give operators one correlation entry point to trace real data across HTTP, database, scheduler, outbox, workers, and providers, with actionable quality/availability signals and safe recovery procedures.

#### Current implementation and dependencies

- Basic Prometheus request count/latency exists and OpenTelemetry packages are installed, but tracing is incomplete. Structured logs do not consistently bind context across HTTP, Celery, outbox, SQL, and providers. HTTP metrics currently select the path before routing and can label arbitrary unmatched raw URL paths, creating unbounded cardinality and possible identifier leakage.
- The runbook names queue/outbox/projection/source-quality metrics not fully emitted; readiness often checks only schema availability.
- Requires Sprints 24-32, including Sprint 25c tenant context, so all production workflows expose stable identifiers and operational states.

#### Implementation and interface requirements

- Instrument FastAPI, SQLAlchemy, Celery, Redis, outbox dispatch, source scheduling, and outbound HTTP clients with OpenTelemetry and consistent sampling/export failure behavior.
- Propagate request, correlation, causation, source-run/item, outbox/message, provider-operation, CRM, mail, and meeting identifiers across all boundaries.
- Emit API RED metrics and bounded-cardinality workflow metrics for sources/parsers, queues/outbox, review, providers, mail, CRM, and meetings.
- Resolve metric route templates only after routing and use one fixed label for unmatched/unknown paths. Never label metrics with raw paths, tenant IDs/slugs, record IDs, URLs, emails, provider messages, queries, exception text, or other attacker/customer-controlled values.
- Protect `/metrics` with metrics-collector workload identity, keep readiness cluster-internal, and disable docs/OpenAPI/Redoc by default as required by Sprint 25b.
- Centralize structured exception classification and redaction before logs, audit, persisted health/error fields, events, traces, metrics, or API responses; specifically strip credentials, authorization/cookies, query secrets, mail content, provider payloads, and personal data.
- Emit quality metrics for parse yield, required-field completeness, duplicates, suspicious domains, resolution ambiguity, and corroboration quality, with defined denominators.
- Add service-specific readiness for mandatory local dependencies; remote provider health affects degraded state, not liveness.
- Add alerts with severity, owner, threshold/window, investigation, safe mitigation, escalation, and recovery evidence.
- Redact tokens, email content, prohibited personal data, article bodies, and provider secrets from logs/traces/metrics.
- Add parser-drift canaries that can pause only unsafe sources while independent pipelines continue.
- Publish trace/log field and metric contracts, cardinality budgets, readiness/degraded schemas, dashboards, alert ownership, and correlation search/reporting entry points.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Never use unbounded IDs/URLs/emails/tenant identifiers as metric labels, expose sensitive payloads, persist raw provider exceptions, or make liveness depend on remote providers. Cross-tenant operational views use approved de-identified aggregates, not raw shared traces or support access.
- Test trace propagation across HTTP/outbox/worker/database/provider, sampling context, tenant separation, raw/404/dynamic path floods, label cardinality budgets, exception and provider-secret redaction, protected metrics, readiness, and telemetry-export outages.
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
- Requires Sprints 25b-25c and 27 plus tenant-scoped lineage/provider states from Sprints 28-33.

#### Implementation and interface requirements

- Add tenant-scoped authoritative versioned policy records for source permission, lawful basis, participant reuse, retention, suppression, approval, outreach eligibility, provider enablement, support approval, residency, export, analytics, and AI/data use, with effective dates and immutable hashes.
- Resolve policy server-side at decision time and persist exact version/hash. Caller snapshots are advisory input only and cannot override authority.
- Add administrator/governance policy APIs with optimistic versions, idempotency, effective dates, preview/validation, permissions, and complete audit history.
- Add retention evaluation and deletion/anonymization jobs for raw items, evidence, contacts, email payloads, and provider responses. Preserve only legally required minimal suppression identifiers.
- Add data-subject request intake, identity/authorization verification, discovery, export, restriction, deletion, provider action/reference tracking, and completion evidence.
- Add scoped legal holds preventing deletion while allowing reporting of held-expired data.
- Hash-chain or sign audit entries, protect tenant/environment-scoped signing keys, periodically verify continuity/signatures, and anchor summaries externally when configured.
- Include tenant, actor type, membership/support/break-glass grant, session/tenant switch, record reads and writes, export/download, automation/integration/policy changes, denial, placement, and provider action in immutable audit. Integrity verification must detect deletion, reordering, alteration, cross-tenant substitution, and missing expected events.
- Add governance reports for violations, retention failures, stale evidence, prohibited reuse, unauthorized activation attempts, subject-request status, holds, and audit integrity.
- Publish policy/DSR/hold/integrity APIs and event schemas, migrations, retention schedules, deletion/anonymization semantics, provider coordination, signature/key rotation, and failure recovery.

#### Safety, tests, and acceptance

- Verification must explicitly cover unit, database/integration, public/event contract, browser/operator UI, deployment/Helm, and bounded staging/live-provider layers affected by this sprint; ordinary CI stays deterministic and any inapplicable layer must be justified in the test plan.
- Do not accept favorable caller policy, delete held data, erase required suppression protection, expose one subject's data to another, or rewrite audit history.
- Test policy-version races/retroactivity, effective boundaries, retention clocks, holds, cascades, anonymization, suppression preservation, signing/key rotation, altered/missing audit entries, and job crashes/retries.
- End-to-end DSR tests span canonical records, CRM references, sequencing, meetings, raw evidence, provider actions, and audit evidence. Browser/contract tests cover all admin/governance roles and optimistic conflicts.
- Acceptance: callers cannot bypass policy; expired data is removed/anonymized on schedule while holds remain; DSRs produce complete tenant-complete evidence without exposing another tenant; support/break-glass activity is attributable; integrity verification detects alterations and gaps.

#### Documentation requirements

- Update affected governance, ingestion, enrichment, email, scoring, CRM, sequencing, meeting, reporting, console, gateway docs plus architecture, pipeline/dashboard specs, runbook, relevant ADRs, secrets guide for signing keys, and root README.
- Apply Sprint 24's complete scoped documentation rule and final consistency search.

### Sprint 35 - Kubernetes Production Platform, Disaster Recovery, and Go-Live

#### Objective and production outcome

Deliver a hardened Kubernetes/Helm production profile with recoverable data services, workload-aware scaling, immutable promotion, tested failure recovery, and evidence-based go-live approval.

#### Current implementation and dependencies

- deploy/helm/ghostrecon/ deploys APIs, one worker, one scheduler, bundled PostgreSQL/Redis, and CPU-based API HPAs.
- TLS ingress, application network policies, disruption budgets, topology spreading, workload autoscaling, backups, and tested restore/regional recovery are absent. Application pods share one service account and do not disable token automount; the third-party email-verifier deployment lacks the main workload security context. Secrets remain SOPS/Age placeholders; no load/soak/rollback evidence proves readiness.
- Requires completion of Sprints 24-34, including Sprint 25c shared/dedicated tenant placement, and signed E1 evidence before staging burn-in. Kubernetes/Helm is production; Compose remains local-only troubleshooting.

#### Implementation and interface requirements

- Require managed PostgreSQL/Redis for E2 while retaining bundled stores only for local/test profiles; make durability/HA capability differences explicit and validated.
- Implement Sprint 25c `TenantPlacement`: shared managed pools by default and dedicated databases/regions/storage/index namespaces for contractual, regulatory, residency, or enhanced-isolation tenants. Automate placement provisioning, migration, backup/PITR/restore, failover, key/secret rotation, capacity, deletion, and evidence.
- Add TLS ingress, default-deny application/egress NetworkPolicies, pod disruption budgets, anti-affinity/topology spreading, distinct least-privilege service accounts/RBAC, `automountServiceAccountToken: false` by default, RuntimeDefault seccomp, security contexts for every first/third-party workload including email verifier, and resource/ephemeral-storage budgets.
- Separate queues/workers by workload and scale by queue lag/work metrics rather than API CPU alone. Guarantee one active scheduler through leader election or equivalent durable scheduling.
- Add PostgreSQL backups, PITR, automated restore verification, and migration rollback/roll-forward procedures. Define Redis persistence/recovery for its queue/coordination role.
- Enforce immutable image provenance/signing, vulnerability policy, SBOM linkage, secret rotation, and controlled environment promotion.
- Lock and hash Python production/dev dependencies; build reproducibly with a multi-stage minimal runtime that excludes compilers/download tools; add `.dockerignore`; scan dependencies, secrets, source, manifests, and images; fail policy on supported exploitable vulnerabilities rather than relying only on Bandit or `ignore-unfixed` image results.
- Add `SECURITY.md`, security contact, coordinated disclosure/intake, severity and remediation SLAs, supported-version policy, customer advisory process, CODEOWNERS for security/release paths, dependency-update automation, protected release approvals, and signed attestations linking source, tests, image, SBOM, manifests, and promotion.
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
- Go-live requires successful security, recovery, tenant-isolation, load, staging-soak, and real-data end-to-end exercises with signed owners and explicit rollback criteria, plus an independent penetration test against the final shared-SaaS architecture and verified remediation.
- Acceptance: production topology is hardened and observable, shared and dedicated tenant data recovery meets objectives, deployment is reproducible/promotable/rollback-capable, outages remain isolated, no unresolved Critical or High findings remain, and E2 evidence is owner-signed.

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
- Local demo, Compose, deterministic-provider, and scanner results never satisfy E1 or E2 and must not be presented as enterprise-readiness evidence.
- The first implementation priority is fixing the missing migration/schema problem because it blocks all reporting-backed dashboard pages.
