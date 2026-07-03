# governance-service Technical README

## Responsibilities

- Evaluate source content-storage and participant-reuse policy.
- Validate deterministic incident corroboration inputs and own audited analyst decisions.
- Evaluate suppression and store do-not-contact state.
- Track lawful basis, retention class, policy version, approval/rejection, and revocation.
- Own immutable audit events for decisions, replay, and policy-sensitive state changes.

## Interfaces

Implemented baseline:

- `POST /v1/suppressions/evaluate`

Target interfaces:

- `POST /v1/review/candidates/{candidate_id}/approve`
- `POST /v1/review/candidates/{candidate_id}/reject`
- `POST /v1/review/candidates/bulk-decision`
- policy/corroboration administration endpoints restricted by role.

Every mutation requires actor, reason where required, optimistic version, `Idempotency-Key`, and policy/evidence snapshot.

## Rules

- Suppression applies by email, domain, contact, company, channel, and applicable source/target scope.
- Published participant contact extraction/export requires source reuse state `allowed` with evidence and intended scope.
- `unknown` and `prohibited` fail closed.
- Incidents start `candidate`; corroboration requires authoritative disclosure, independent-source threshold, or audited analyst decision.
- Generated/verified email does not establish lawful basis or outreach approval.
- CRM export approval does not establish sequence eligibility.
- The most restrictive current rule wins when records conflict.

## Failure Modes

- Database/policy projection unavailable: deny policy-sensitive eligibility.
- Conflicting policy/suppression rows: apply the most restrictive rule and alert.
- Stale optimistic version/evidence: reject decision and require refresh.
- Replay/export requested for ineligible target: reject and audit.
- Audit write failure: fail the mutation; never commit unaudited approval.

## Testing

- Source reuse `allowed`/`unknown`/`prohibited` enforcement tests.
- All incident corroboration paths and analyst-override audit tests.
- Database-backed suppression and retention tests.
- Approval invalidation, optimistic conflict, bulk decision, and replay authorization tests.
- CRM-versus-outreach approval separation tests.
