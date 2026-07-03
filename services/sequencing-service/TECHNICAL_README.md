# sequencing-service Technical README

## Responsibilities

- Evaluate sequence eligibility.
- Schedule future sequence steps.
- Enforce per-domain, per-sender, and per-channel rate limits.
- Pause or end sequences when replies, meetings, opportunities, bounces, or opt-outs occur.

## Interfaces

- `POST /v1/sequences/evaluate`

## Safety Rules

- Suppression checks run immediately before sending.
- Approval state must be current.
- Replay of outbound actions must be explicit and audited.

## Failure Modes

- SMTP outage: pause sends and retry within budget.
- IMAP outage: continue no-send safety checks but delay reply processing.
- Bounce spike: pause affected domain or sender.

## Testing

- Eligibility tests.
- Suppression-before-send tests.
- Rate-limit tests.
- SMTP/IMAP integration tests in later sprints.
