# console-service Technical README

## Responsibilities

- Render the internal operator dashboard for implemented intelligence plus review/reporting workflows.
- Consume `reporting-service` read APIs for events, incidents, watchlists, queues, exports, KPIs, source health, and freshness.
- Call owning feature-service write APIs through the gateway; never mutate reporting projections directly.
- Provide human-in-the-loop controls for intelligence corroboration, enrichment, CRM eligibility, replay, and policy-sensitive actions.
- Enforce CSRF protection, authenticated sessions, server-side role checks, optimistic versions, and idempotency keys.

Sprint 8 does not add dashboard UI dependencies. The future dashboard implementation should use Python Dash inside this service boundary and keep callbacks read-only against reporting APIs unless explicitly invoking gateway mutations.

## Interfaces

Implemented baseline:

- `GET /`
- `GET /v1/review/candidates`
- `GET /v1/review/crm-targets`
- `POST /v1/review/candidates/{candidate_id}/approve`
- `POST /v1/review/candidates/{candidate_id}/reject`
- `POST /v1/review/candidates/bulk-decision`

Target view routes:

- `GET /events`, `GET /events/{event_id}`
- `GET /incidents`, `GET /incidents/{incident_id}`
- `GET /watchlists`
- `GET /review/enrichment`, `GET /review/candidates`
- `GET /crm/exports`, `GET /crm/exports/{batch_id}`
- `GET /operations/sources`

Mutation forms map to APIs specified in `docs/specifications/intelligence-pipeline.md`; routes do not implement feature business rules locally.

Future Dash setup:

- Mount Dash under the existing console application and service deployment.
- Use `/v1/reporting/*` and `/v1/kpis/catalog` for read callbacks.
- Pass actor, role, reason, optimistic version, and idempotency headers to gateway mutations.
- Do not add an independent dashboard service, datastore, or direct canonical-table access from UI callbacks.

## Permissions and UI Safety

- Roles are `viewer`, `analyst`, `governance_reviewer`, and `administrator`.
- Every mutation repeats authorization in the owning API and records actor/reason/audit context.
- Bulk review requires homogeneous policy context, a bounded count, preview, and per-item outcomes.
- Unknown/prohibited participant reuse disables actions in UI and API; the UI control alone is not the enforcement boundary.
- CRM-target approval controls never invoke CRM export or sequence enrollment.
- Render source content as escaped text; sanitize bounded excerpts and external links.

## Failure Modes

- Reporting unavailable: show degraded state and no fabricated/empty-success results.
- Projection stale: display watermark; block mutations whose evidence/policy must be current.
- Feature service unavailable: keep read view where safe and disable its mutations.
- Optimistic conflict: reload changed evidence/policy before allowing a new decision.
- Mutation failure: show correlation/audit ID and retryability without automatically retrying writes.
- Authentication/authorization failure: fail closed.

## Testing

- HTML and navigation smoke tests.
- Role/CSRF/server-side authorization tests.
- Map/calendar table-alternative and WCAG keyboard tests.
- Filter URL, cursor pagination, and stale/degraded-state tests.
- Participant-permission and policy-change invalidation tests.
- Bulk decision conflict/idempotency/audit tests.
- CRM partial-failure/reconciliation view tests.
