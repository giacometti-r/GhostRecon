# governance-service Technical README

## Responsibilities

- Evaluate source content-storage and participant-reuse policy.
- Validate deterministic incident corroboration inputs and own audited analyst decisions.
- Evaluate suppression and store do-not-contact state.
- Track lawful basis, retention class, policy version, approval/rejection, and revocation.
- Own immutable audit/outbox events for decisions, incident corrections, suppressions, inert CRM targets, replay, and policy-sensitive state changes.

## Interfaces

- `POST /v1/suppressions`
- `POST /v1/suppressions/evaluate`
- `GET /v1/review/candidates`
- `GET /v1/review/crm-targets`
- `POST /v1/review/candidates/{candidate_id}/approve`
- `POST /v1/review/candidates/{candidate_id}/reject`
- `POST /v1/review/candidates/bulk-decision`
- `POST /v1/governance/incidents/{incident_id}/corroborate`
- `POST /v1/governance/incidents/{incident_id}/reject`

Every mutation requires actor, reason where required, optimistic version, `Idempotency-Key`, and policy/evidence snapshot.

## Rules

- Suppression applies by email, domain, contact, company, channel, and applicable source/target scope.
- Published participant contact extraction/export requires source reuse state `allowed` with evidence and intended scope.
- `unknown` and `prohibited` fail closed.
- Incidents start `candidate`; corroboration requires authoritative disclosure, independent-source threshold, or audited analyst decision.
- Generated/verified email does not establish lawful basis or outreach approval.
- Review approval creates an inert CRM target with `export_status=not_exported`; CRM export remains a separate Sprint 9 workflow.
- CRM target approval does not establish sequence eligibility.
- The most restrictive current rule wins when records conflict.
- Bulk review requires open candidates, one candidate type, one policy snapshot hash, a bounded count, and per-candidate optimistic versions.

## Failure Modes

- Database/policy projection unavailable: deny policy-sensitive eligibility.
- Conflicting policy/suppression rows: apply the most restrictive rule and alert.
- Stale optimistic version/evidence: reject decision and require refresh.
- Missing lineage, unknown/prohibited reuse, uncorroborated incident, active suppression, missing lawful basis, missing/expired retention, or stale evidence: fail closed and reject approval.
- Replay/export requested for ineligible target: reject and audit.
- Audit write failure: fail the mutation; never commit unaudited approval.

## Testing

- Source reuse `allowed`/`unknown`/`prohibited` enforcement tests.
- All incident corroboration paths and analyst-override audit tests.
- Database-backed suppression and retention tests.
- Approval invalidation, optimistic conflict, bulk decision, and replay authorization tests.
- CRM-versus-outreach approval separation tests.
- Route tests for approval/rejection, CRM-target reads, suppression creation, and incident analyst decisions.
