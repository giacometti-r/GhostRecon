# email-intelligence-service

## Purpose

`email-intelligence-service` generates likely business-email candidates for already eligible public business contacts and validates them through the open-source `umuterturk/email-verifier` service. It supports event/incident intelligence without using paid contact databases.

Source permission and role scope are prerequisites. The service cannot make an unknown/prohibited participant reusable, turn breached data into a candidate, approve CRM export, or authorize outreach.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=email-intelligence-service`
- Verifier env: `GHOSTRECON_EMAIL_VERIFIER_URL`

## Dependencies

- Eligible canonical contacts with source/event/incident lineage and policy version.
- `email-verifier` sidecar/service and its Redis domain cache.
- PostgreSQL for candidates, verification payloads, confidence, and lineage.
- Governance service for current reuse, suppression, retention, and review state.

## Operations

- Generated addresses remain candidates until verified and reviewed as policy requires.
- Reject requests without eligible source lineage or permitted public-business role scope.
- Treat role-based, disposable, catch-all, ambiguous, and stale results according to versioned policy.
- Re-check policy before promotion; a later source-policy change invalidates eligibility.
- Monitor verifier health, DNS failure, candidate yield, verification outcomes, policy blocks, and stale candidates.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=email-intelligence-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
