# scoring-routing-service

## Purpose

`scoring-routing-service` computes explainable fit, relevance, recency, evidence, and confidence scores for event- and incident-derived candidates. It routes candidates to rejection, enrichment, analyst review, CRM-target eligibility evaluation, or later nurture/sequence evaluation.

Sprint 7 implements `sprint7.v1` candidate scoring. Scoring cannot override source permission, corroboration, suppression, retention, lawful basis, or analyst approval.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=scoring-routing-service`

## Dependencies

- Canonical accounts, contacts, events, incidents, source/evidence lineage, and lead signals.
- Governance service for corroboration, reuse, suppression, retention, and approval state.
- CRM service for optional ownership/context after approved export.

## Operations

- Version score weights, thresholds, feature definitions, and policy references.
- Keep `cyber_event` and `security_incident` source performance separately observable.
- Explain every score with contributing facts and freshness.
- Route fail-closed policy blockers to rejection, ambiguous evidence to review, and high-confidence candidates to CRM-target review.
- Monitor score distribution, confidence calibration, threshold outcomes, false positives, and routing failures.

## APIs

- `POST /v1/scoring/lead` keeps the legacy account/signal scoring contract.
- `POST /v1/scoring/candidates` persists a `CandidateScore`, emits `lead.scored`, and creates a review candidate for non-rejected candidate routes.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=scoring-routing-service uvicorn ghostrecon.service_apps.runtime:app --reload
```

## Verification

```bash
pytest tests/unit/test_scoring.py tests/unit/test_enrichment_routes.py
```
