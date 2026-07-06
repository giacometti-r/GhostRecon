# scoring-routing-service Technical README

## Responsibilities

- Score fit, event/incident relevance, evidence quality, confidence, recency, and signal strength.
- Explain score contributions, missing context, policy blockers, and configuration version.
- Route records to rejection, analyst review, or CRM-target review without CRM/export side effects.
- Persist `CandidateScore` records and publish `lead.scored` plus review-request events when human review is needed.

## Interfaces

- `POST /v1/scoring/lead`
- `POST /v1/scoring/candidates`

The implemented candidate schema includes target type/ID, canonical origin ID, source lineage, account/contact context, signals, evidence/source freshness, incident corroboration, participant reuse, suppression, retention, lawful-basis, and policy snapshot fields. The active config version is `sprint7.v1`.

## Data and Policy Rules

- Never convert `unknown`/`prohibited` participant reuse into eligibility regardless of score.
- Uncorroborated incidents fail closed for CRM-target review.
- Keep source confidence distinct from fit/relevance; high fit does not repair weak evidence.
- Score explanations reference canonical facts and evidence IDs, not unlicensed body text.
- Version configuration and retain the exact version with every result.
- Do not overwrite CRM ownership outside explicit CRM-service logic.
- Score routes are `rejected`, `needs_review`, and `crm_target_review`; approval remains governance-owned.

## Failure Modes

- Missing account/evidence context: score conservatively and explain missing fields.
- Bad/incompatible signal payload: reject or quarantine with schema version.
- Stale evidence/policy: mark result stale and prevent CRM-target promotion.
- Routing ambiguity: send to human review.
- Feature drift: compare distributions/calibration and roll back configuration, not historical audits.
- Missing lineage, missing lawful basis, active suppression, stale evidence, or stale/unknown policy: route to `rejected` with policy blockers.

## Testing

- Threshold and source-taxonomy unit tests.
- Golden-file score-explanation tests for event and incident candidates.
- Evidence/corroboration/reuse hard-block tests.
- Configuration-version and regression/calibration tests.
- Stale-input and ambiguous-routing tests.
- Route-contract tests for persisted candidate scoring through the service router.
