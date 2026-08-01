# Intelligence Dashboard Product Specification

## Product Boundary

The intelligence dashboard belongs in the existing `console-service` and is backed by `reporting-service` read models. No separate dashboard service or independent copy of business state is introduced.

The dashboard supports investigation, watchlist management, enrichment review, governance decisions, CRM export, sequencing state, meeting handoff, reconciliation, and source operations. It does not send outreach directly; sequencing actions call backend APIs that enforce approval, suppression, lawful-basis, and rate-limit checks. Meeting actions call the owning meeting-handoff APIs so Google Calendar invites, prep packets, and CRM follow-up sync keep backend policy gates.

Sprint 12 implements the UI with Python Dash mounted at `/` inside `console-service`; Sprints 17 and 18 add the event create/edit, participant enrichment queue, incident governance, and company-watchlist dashboard workflows. The service still exposes FastAPI health, metrics, docs, and `/v1/*` routes before the Dash catch-all route.

## Dash Architecture

- Host Python Dash from `console-service` so operators still use one internal dashboard service.
- Keep Dash read callbacks on `/v1/reporting/*`, `/v1/reporting/kpis/catalog`, `/v1/kpis/catalog`, and documented owning read APIs such as `/v1/sequences/*`.
- Route mutation callbacks through gateway/owning APIs, never reporting projections or canonical tables.
- In the current local/test demo, propagate legacy `X-Actor`, `X-Operator-Role`, idempotency keys, reason text, and optimistic versions to owning APIs. Strict staging/production profiles reject the identity headers; OIDC sessions and authenticated propagation remain Sprint 25b work.
- Do not create an independent dashboard datastore or direct canonical-table access from UI callbacks.
- Treat the dashboard as the operator control plane: stale source visibility, review safety, CRM-export separation, and auditability are required product behavior, not optional visual polish.

## Implemented Routes

- `/`: KPI, source, review, CRM target, and meeting summary.
- `/events` and `/events/{event_id}`: event table, coordinate-backed venue map, create/edit modals, and participant enrichment queue handoff.
- `/incidents` and `/incidents/{incident_id}`: company-specific incident feed/detail, corroborate/reject/revert controls, manual incident modal, and company watchlist promotion.
- `/watchlists` and `/watchlists/{watch_target_id}`: company watch target list/detail, owner, monitoring state, enabled-state toggle, and contact discovery.
- `/review` and `/review/enrichment`: analyst review, bounded visible-page bulk review, contact enrichment, entity resolution queues, and company-domain discovery.
- `/crm/exports` and `/crm/exports/{batch_id}`: CRM target selection, export start, batch detail, and retry failed items.
- `/sequences`: sequence enrollment state and pause/resume/cancel controls.
- `/meetings` and `/meetings/{meeting_id}`: meeting handoff state, prep packet, outcome, cancel, and CRM-sync retry controls.
- `/operations/sources`: reporting-backed source freshness and degraded-state visibility.

## Users and Permissions

| Role | Read access | Mutating access |
| --- | --- | --- |
| `viewer` | Intelligence views, permitted evidence, source health, aggregate export status | None |
| `analyst` | All viewer data plus review details and assigned queues | Create watch targets; approve/reject eligible candidates; initiate exports from approved targets; retry allowed failed items |
| `governance_reviewer` | All analyst data plus policy, suppression, retention, and audit detail | Decide policy exceptions/corroboration with reasons; revoke eligibility; manage retention/suppression decisions |
| `administrator` | All operational data and configuration | Manage source definitions, assignments, replay, degraded-state acknowledgment, and role bindings |

Server-side authorization is required for every action. Hiding a button is not authorization. Permissions, actor, reason, optimistic version, idempotency key, before/after state, and policy version are audited.

Generated-at, stale, projection, and watermark metadata on event and incident detail pages is visible only to the `governance_reviewer` role. Administrators keep operational controls but do not see those governance metadata rows in these detail views.

## Global Interaction Rules

- Every page displays data freshness and degraded dependencies.
- All dates render in the operator-selected timezone while exposing source and UTC values.
- Tables use cursor pagination, stable sorting, shareable filter URLs, and CSV export only for fields the role may view.
- Evidence links open safely and rendered excerpts are sanitized untrusted content.
- Mutations show the exact records and downstream effect before confirmation.
- Bulk actions are bounded and unavailable for mixed policy/reuse states that require different decisions.
- Approval can create CRM eligibility; it cannot enroll or send a sequence.
- CRM export success can make a target available for sequencing review and meeting handoff, but it cannot enroll or send a sequence without separate outreach approval or create a meeting without meeting-specific suppression checks.

## Navigation and Views

The implemented Dash console uses `dcc.Location` as the single routing source for
sidebar tabs, detail links, and pagination links. The sidebar marks the current
section with active styling and `aria-current`; detail routes inherit the active
state from their parent section.

### 1. Global Events

Views:

- large coordinate-backed map for geocoded in-person and hybrid events;
- sortable table for precise review and export; and
- create/edit modals for manually entered event intelligence.

Filters:

- UTC/source date range;
- country, region, and radius;
- in-person, online, hybrid, or unknown format;
- topic, event series, organizer, and source;
- participant availability and participant-reuse state;
- confidence, duplicate/canonical state, and freshness.

Actions:

- open event detail;
- create or edit an event when the role can mutate;
- add an eligible published participant to the enrichment queue with an idempotent action;
- create event-series/topic watch target;
- send an eligible event or permitted participant to review;
- merge/flag a suspected duplicate when authorized; and
- inspect raw-source lineage.

Event detail shows original and normalized time, venue/geography, exact street/city/postcode/country address, topics without bullet artifacts, organizers, all evidence sources, canonical/duplicate history, and published participant roles. Participant rows show the exact source, reuse evidence/state, organization/title as published, resolution confidence, whether contact extraction/CRM export is disabled, and whether the participant has already been queued for enrichment.

### 2. Global Incidents

The incident feed shows:

- affected company/domain context, one row per affected company for multi-company incidents;
- candidate/corroborated/rejected state and corroboration method;
- incident type or attack vector;
- inline evidence families and evidence URLs;
- geography and first/last observed times;
- watchlist state, review state, and freshness.

Filters:

- date window, geography, language, source, and topic;
- affected company/domain/industry;
- attack vector, incident status, confidence band, evidence count;
- global-only, watched, promoted, or follow-on coverage; and
- unresolved entity, disputed, or stale evidence.

Actions:

- open the detail view from the table;
- promote the affected company into a company watchlist only after corroboration;
- approve corroboration, reject a false positive, or revert corroboration when permitted;
- manually add incidents and split multi-company/domain inputs into company-specific rows;
- route eligible company/contact candidates to review; and
- merge duplicate cases with an audit reason.

Promotion must retain and display `origin_incident_id`; it creates or returns an idempotent company watch target and never creates a duplicate incident.

### 3. Watchlists and Follow-On Coverage

Sections:

- company watch targets as the default dashboard presentation;
- owner, created-by, governance-only origin incident, query, enabled state, last monitoring run, and next check;
- new coverage grouped by canonical event/incident case; and
- source/query errors and stale checkpoints.

Actions include open detail, pause/resume monitoring, find contact, create, reassign, edit query, and archive. Editing a target does not rewrite existing source evidence. `Find Contact` runs the OpenSERP LinkedIn search through the enrichment service and stores source/raw-item lineage before creating contact candidates.

### 4. Contact-Enrichment Queue

Each row shows the originating event/incident, company resolution, public role/source, reuse eligibility, domain evidence, proposed contact fields, email verification, source age, and policy blockers.

Actions:

- accept or correct company/contact resolution;
- request/retry permitted enrichment;
- discover or review company website domains from OpenSERP official-website search results;
- reject as wrong person/company, prohibited source, insufficient evidence, or out of scope; and
- move an eligible candidate to analyst review.

The UI never displays breached personal data. Prohibited/unknown participant reuse disables enrichment actions server-side and visually explains the policy reason.

### 5. Analyst Review Queue

Candidate types:

- event;
- event participant;
- incident;
- affected company;
- event contact; and
- incident contact.

Filters include type, owner, age/SLA, source, score, evidence, policy state, corroboration, suppression, verification, and proposed CRM target type.

The decision panel shows evidence, lineage, score reasons, policy version, changed-since-load warning, proposed CRM effect, and explicit separation from outreach. Approve/reject requires a reason where policy specifies. Reject reason codes include duplicate, false positive, wrong entity, prohibited reuse, insufficient evidence, retention/lawful-basis failure, and out of market.

Bulk review:

- requires a preview grouped by candidate type and policy state;
- rejects stale optimistic versions and incompatible mixed selections;
- caps batch size by configuration;
- records a decision result for every candidate; and
- reports partial conflicts without reapplying successful decisions.

### 6. CRM Targets and Export Batches

Target selection is typed: events, event participants, incidents, companies, and incident contacts are selected separately. The UI displays provider mapping, stable match key, dependency order, current approval, policy/suppression state, and any existing provider IDs.

Batch detail shows:

- batch actor, provider/workspace, idempotency key, selection hash, and timestamps;
- per-item target/operation/dependencies, attempts, provider IDs, and status;
- rate-limit state, retry time, typed failure, and reconciliation result; and
- succeeded, failed, skipped-policy, and unresolved totals.

Actions:

- start an idempotent export from approved current targets;
- retry failed retryable items only;
- open reconciliation detail;
- mark an externally resolved mismatch with evidence when authorized; and
- download a permitted audit summary.

No export page auto-enrolls a sequence.

### 7. Sequence State and Outreach Controls

Sequence views show:

- sequence template, owner, channel, active status, and step timing;
- enrollment actor, separate outreach approval reason, current step, next-step time, and pause/completion state;
- outbound attempt status, provider message ID, retry/backoff, and last error;
- reply, bounce, and unsubscribe events with durable suppression linkage; and
- per-domain, per-sender, and per-channel rate-limit state.

Actions:

- create or select an approved sequence template;
- enroll only exported/current CRM targets with explicit outreach approval;
- pause, resume, or cancel an enrollment;
- ingest unsubscribe events; and
- inspect reply/bounce history.

The UI must never offer a send-now bypass. The backend re-checks suppression, lawful basis, verified email, do-not-contact state, approval, and rate limits before each outbound action.

### 8. Source Health

Source cards and table rows show:

- source/adapter, enabled state, owner, and policy review state;
- last attempt/success, checkpoint/watermark, lag versus freshness objective;
- response/error class, retry/backoff, rate-limit state, parse yield, and duplicate rate;
- last schema/selector failure and recent replay; and
- downstream projection freshness.

States are `healthy`, `delayed`, `degraded`, `paused`, and `disabled`. Operators can filter by adapter, kind, owner, state, policy, and freshness breach.

Administrator actions should eventually include pause/resume, bounded test fetch, replay from a durable checkpoint, and degraded-state acknowledgment. Sprint 12 keeps these controls read-only because owning source-operations APIs do not exist yet. The UI must not expose raw credentials or unrestricted arbitrary URLs.

## Reporting-Service Read APIs

The console consumes target read endpoints:

- `GET /v1/reporting/events`
- `GET /v1/reporting/events/{event_id}`
- `GET /v1/reporting/incidents`
- `GET /v1/reporting/incidents/{incident_id}`
- `GET /v1/reporting/watch-targets`
- `GET /v1/reporting/review-queue`
- `GET /v1/reporting/crm-targets`
- `GET /v1/reporting/meetings`
- `GET /v1/reporting/meetings/{meeting_id}`
- `GET /v1/reporting/source-health`
- `GET /v1/reporting/kpis/catalog`

Sequencing write/read actions use the owning `/v1/sequences/*` APIs through the gateway. Meeting booking, prep-packet generation, outcome recording, cancellation, availability, and CRM-sync retry use `/v1/meetings/*` and `/v1/calendar/availability` through the gateway. Reporting projections can add workflow summaries later, but dashboard actions must not query or mutate sequencing or meeting tables directly.

Event create/edit actions use `POST /v1/intelligence/events/manual` and `PATCH /v1/intelligence/events/{event_id}` with idempotency keys and optimistic event versions. Incident actions use `POST /v1/intelligence/incidents/manual`, `POST /v1/governance/incidents/{incident_id}/corroborate`, `POST /v1/governance/incidents/{incident_id}/reject`, `POST /v1/governance/incidents/{incident_id}/revert`, and `POST /v1/intelligence/incidents/{incident_id}/promote-to-watchlist`, all through the gateway and owner services.

Each response includes `generated_at`, source watermark(s), projection version, stale boolean, and degraded dependencies. Collection endpoints accept `limit`, `cursor`, and stable filters. The current local/test dashboard also sends legacy operator role context through `X-Operator-Role`; strict staging/production rejects it, and the new Sprint 25 permission model is not yet connected to route or projection enforcement. Write actions call the owning feature service through the gateway, not reporting projections.

## KPI Families

- discovery coverage by geography/language/source/topic;
- source freshness, fetch success, parse yield, and duplicate rate;
- events/participants by reuse eligibility;
- incident candidates, corroboration time/method, false-positive rate, and watchlist follow-on coverage;
- entity/contact resolution yield and correction rate;
- email candidate verification and rejection rate;
- review age/SLA, approval/rejection, bulk conflict, and policy-block rate;
- CRM batch latency, item success/partial failure, retry, and reconciliation age; and
- sequence enrollment, send, reply, bounce, unsubscribe, and rate-limit outcomes; and
- meetings booked, prep-packet latency, outcome rate, CRM sync failures, and follow-up task completion after approved CRM activation.

## Empty, Loading, Error, and Stale States

- Empty state distinguishes “no matching data” from “source has never succeeded.”
- Failed dashboard API reads show endpoint/status context directly on the route so operators can distinguish gateway/reporting outages from empty data.
- Partial dependency failure renders available read data, names the degraded dependency, and blocks unsafe mutations.
- Stale evidence or policy projection blocks approval/export when the owning policy requires current state.
- Long-running actions return an operation/batch ID; the UI polls bounded status endpoints and can be safely refreshed.
- A failed mutation displays correlation/audit ID and whether retry is safe; it never silently repeats a write.

## Sprint 25a Security Boundary

The shared HTTP perimeter now applies to the console and gateway. In staging/production it rejects
legacy actor/role headers and reserved internal OBO/service-authorization headers, adds security
response headers, and applies transport bounds. The dashboard still renders a demo role selector
and sends the legacy headers, so the current UI authentication/authorization flow is local/test-only.
The new role/permission and assurance primitives are not yet wired to Dash callbacks, API routes,
sessions, or denied/expired/step-up UX. `/docs`, `/metrics`, readiness, and owner-service routes also
remain outside operation-policy enforcement.

## Accessibility and Security

- Meet WCAG 2.1 AA for keyboard navigation, focus order, labels, non-color state indicators, tables, dialogs, and map alternatives.
- Provide a table alternative for every map/calendar result.
- Escape all source-derived text and sanitize any permitted excerpt.
- Protect forms with CSRF controls, short-lived authenticated sessions, and server-side authorization.
- Redact credentials, provider tokens, full raw payloads, and disallowed personal data from views and logs.

## Acceptance Criteria

- Events can be viewed consistently in map, calendar, and table forms with the specified filters.
- Event detail exposes source timezone/original time, lineage, participant roles, and enforceable reuse state.
- Incident feed exposes company/domain context, attack vector, inline evidence URLs, geography, status, corroboration/revert controls, and watchlist eligibility state.
- Promoting an incident preserves the originating incident and follow-on coverage joins the same case.
- Unknown/prohibited participant reuse disables contact and export actions in both UI and API authorization tests.
- Contact and analyst queues expose policy/evidence context and support audited, conflict-safe bulk review.
- Review approval creates only current CRM eligibility and never outreach enrollment.
- Typed CRM target selection, dependency ordering, idempotent batch retry, rate limits, partial failures, and reconciliation are visible and tested.
- Sequence enrollment requires separate outreach approval, and send/reply/bounce/unsubscribe states are visible without exposing a backend bypass.
- Meeting handoff requires an exported/current CRM target, shows Google Calendar event state, exposes prep-packet/outcome/follow-up task status, and surfaces retryable CRM sync failures.
- Source and reporting staleness are visible even when process health endpoints are green.
- Role tests prove viewers cannot mutate, analysts cannot change source policy, and governance/admin actions require appropriate reasons.
- Linkable filter state, cursor pagination, table map-alternatives, sanitized excerpts, and WCAG keyboard flows pass acceptance tests.
