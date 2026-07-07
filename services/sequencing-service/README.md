# sequencing-service

## Purpose

`sequencing-service` owns in-house sequence eligibility, enrollment, and outbound execution after separate outreach approval. It evaluates suppression, approval, score thresholds, channel policy, lawful basis, verified email state, and rate limits before any outreach action.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=sequencing-service`
- SMTP env: `GHOSTRECON_SMTP_HOST`, `GHOSTRECON_SMTP_PORT`, `GHOSTRECON_SMTP_USERNAME`, `GHOSTRECON_SMTP_PASSWORD`, `GHOSTRECON_SMTP_FROM_ADDRESS`
- IMAP env: `GHOSTRECON_IMAP_HOST`, `GHOSTRECON_IMAP_PORT`, `GHOSTRECON_IMAP_USERNAME`, `GHOSTRECON_IMAP_PASSWORD`, `GHOSTRECON_IMAP_MAILBOX`

## APIs

- `POST /v1/sequences/evaluate`
- `POST /v1/sequences`
- `POST /v1/sequences/enrollments`
- `GET /v1/sequences/enrollments`
- `GET /v1/sequences/enrollments/{enrollment_id}`
- `POST /v1/sequences/enrollments/{enrollment_id}/pause`
- `POST /v1/sequences/enrollments/{enrollment_id}/resume`
- `POST /v1/sequences/enrollments/{enrollment_id}/cancel`
- `POST /v1/sequences/unsubscribe`

Worker tasks:

- `ghostrecon.process_due_sequence_steps`
- `ghostrecon.poll_sequence_inbound_email`

## Dependencies

- Governance service for suppression and lawful basis.
- Scoring service for eligibility.
- CRM service/export state for exported/current CRM targets.
- SMTP/IMAP providers through adapter protocols.
- PostgreSQL and Redis for schedule state and rate limits.

## Operations

- Never send if suppression checks fail.
- Never enroll from CRM export alone; exported CRM targets require separate outreach approval.
- Strategic or high-risk accounts require approval before enrollment.
- Re-check verified email, lawful basis, do-not-contact, suppression, and rate limits immediately before every send.
- Replies complete enrollments, bounces pause affected enrollments, and unsubscribes create durable suppression evidence.
- Monitor send queue depth, bounce rate, reply rate, unsubscribe rate, and rate-limit usage.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=sequencing-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
