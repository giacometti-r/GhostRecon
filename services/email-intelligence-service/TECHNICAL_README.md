# email-intelligence-service Technical README

## Responsibilities

- Validate that the originating public contact is eligible for email candidate generation.
- Generate candidates from configured and organization-learned business patterns.
- Call `umuterturk/email-verifier` for syntax, domain, MX, disposable, role-based, alias, and supported ambiguity checks.
- Persist confidence, verification status/payload, source policy/version, and event/incident lineage.
- Publish `email.candidate_generated` and `email.verified` events without implying CRM or outreach approval.

## Interfaces

- `POST /v1/email/candidates`
- `POST /v1/email/verify`
- Worker task: `ghostrecon.generate_email_candidates`

Target requests require `contact_id`, origin type/ID, source-item IDs, reuse eligibility, role scope, and policy version. The service re-reads current policy rather than trusting a caller-supplied boolean alone.

## Data Rules

- Lead origins include `cyber_event` and `security_incident`.
- Event participant candidates require explicit reusable-source scope.
- Incident contacts must be public business roles in security, IT, risk, or communications.
- Breached-data provenance, private addresses, and personal/non-business addresses are rejected.
- Candidate dedupe keys include normalized email and canonical contact/account.
- Verification is evidence, not consent, lawful basis, CRM approval, or outreach approval.

## Failure Modes

- Verifier unavailable/DNS timeout: keep candidate in `pending_verification` and retry within budget.
- Source policy changed: mark eligibility invalid and stop downstream promotion.
- Catch-all/ambiguous response: require review; do not label verified.
- Missing lineage: reject request with typed policy error.
- Conflicting contact identity: route to entity-resolution review.

## Testing

- Pattern generation and organization-pattern version tests.
- Verifier adapter and batch tests.
- Candidate dedupe and stale-verification tests.
- Participant permission and incident-role-scope tests.
- Breached/private-address rejection tests.
- Policy invalidation and no-CRM/no-sequence-side-effect tests.
