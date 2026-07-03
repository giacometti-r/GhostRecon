# scoring-routing-service Technical README

## Responsibilities

- Score fit, event/incident relevance, evidence quality, confidence, recency, and signal strength.
- Explain score contributions, missing context, policy blockers, and configuration version.
- Route records to enrichment, review, rejection, CRM-target evaluation, or later sequence eligibility.
- Publish `lead.scored` and versioned routing events.

## Interfaces

- `POST /v1/scoring/lead`

Target schema extends source taxonomy with `cyber_event` and `security_incident`, canonical origin ID, evidence/source freshness, incident corroboration, participant reuse, entity-resolution confidence, and policy version.

## Data and Policy Rules

- Never convert `unknown`/`prohibited` participant reuse into eligibility regardless of score.
- Uncorroborated incidents may be ranked for investigation but cannot be represented as corroborated.
- Keep source confidence distinct from fit/relevance; high fit does not repair weak evidence.
- Score explanations reference canonical facts and evidence IDs, not unlicensed body text.
- Version configuration and retain the exact version with every result.
- Do not overwrite CRM ownership outside explicit CRM-service logic.

## Failure Modes

- Missing account/evidence context: score conservatively and explain missing fields.
- Bad/incompatible signal payload: reject or quarantine with schema version.
- Stale evidence/policy: mark result stale and prevent CRM-target promotion.
- Routing ambiguity: send to human review.
- Feature drift: compare distributions/calibration and roll back configuration, not historical audits.

## Testing

- Threshold and source-taxonomy unit tests.
- Golden-file score-explanation tests for event and incident candidates.
- Evidence/corroboration/reuse hard-block tests.
- Configuration-version and regression/calibration tests.
- Stale-input and ambiguous-routing tests.
