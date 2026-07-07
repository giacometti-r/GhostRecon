# sequencing-service Technical README

## Responsibilities

- Evaluate sequence eligibility.
- Persist sequence templates, ordered steps, enrollments, outbound attempts, inbound events, and suppression linkage.
- Schedule and execute due sequence steps through SMTP.
- Poll IMAP for replies, bounces, and unsubscribe signals.
- Enforce per-domain, per-sender, and per-channel rate limits.
- Pause or end sequences when replies, meetings, opportunities, bounces, or opt-outs occur.

## Interfaces

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

## Data Rules

- `Sequence` and `SequenceStep` define reusable email templates and timing.
- `SequenceEnrollment` requires an exported/current CRM target and explicit outreach approval.
- `OutboundEmail` records every send attempt, provider message ID, retry state, and failure.
- `InboundEmailEvent` records reply, bounce, and unsubscribe events from IMAP or webhook-style ingestion.
- `SequenceSuppressionEvent` links unsubscribe/suppression evidence back to the affected enrollment when known.

## Safety Rules

- Suppression checks run immediately before sending.
- Lawful basis, verified email status, do-not-contact state, and approval state run immediately before sending.
- CRM export approval does not authorize outreach; sequence enrollment has its own approval reason.
- Rate limits are enforced per recipient domain, sender, and channel before SMTP execution.
- Approval state must be current.
- Replay of outbound actions must be explicit and audited.

## Events

- `sequence.enrolled`
- `sequence.paused`
- `sequence.completed`
- `email.sent`
- `reply.received`
- `bounce.received`
- `unsubscribe.received`

## Failure Modes

- SMTP outage: pause sends and retry within budget.
- IMAP outage: continue no-send safety checks but delay reply processing.
- Bounce spike: pause affected domain or sender.
- Unsubscribe ingestion: create active suppression and suppress active enrollments for the address.
- Rate-limit breach: defer only affected due sends and preserve the enrollment state.

## Testing

- Eligibility tests.
- Suppression-before-send tests.
- Rate-limit tests.
- Route contract tests for enrollment and unsubscribe controls.
- SMTP/IMAP adapter tests with fakes/mocks; no unit test should call a live provider.
