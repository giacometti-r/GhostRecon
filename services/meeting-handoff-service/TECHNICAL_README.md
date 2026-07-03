# meeting-handoff-service Technical README

## Responsibilities

- Build prep packets with account summary, stakeholder map, security priorities, questions, and risks.
- Sync meeting status and follow-up tasks through CRM-service.
- Publish `meeting.booked` and handoff events in future sprints.

## Interfaces

- `POST /v1/meetings/prep-packet`

## Failure Modes

- Missing contacts: generate account-only packet and flag gap.
- Missing signals: generate generic discovery questions.
- CRM sync failure: retain packet and retry sync.

## Testing

- Packet generation tests.
- Missing-data fallback tests.
- CRM sync retry tests in later sprints.
