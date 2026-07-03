# sequencing-service

## Purpose

`sequencing-service` owns in-house sequence eligibility and future outbound execution. It evaluates suppression, approval, score thresholds, and channel policy before any outreach action.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=sequencing-service`

## Dependencies

- Governance service for suppression and lawful basis.
- Scoring service for eligibility.
- SMTP/IMAP providers in later sprints.
- PostgreSQL and Redis for schedule state and rate limits.

## Operations

- Never send if suppression checks fail.
- Strategic or high-risk accounts require approval.
- Monitor send queue depth, bounce rate, reply rate, unsubscribe rate, and rate-limit usage.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=sequencing-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
