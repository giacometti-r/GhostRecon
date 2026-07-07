# meeting-handoff-service Technical README

## Responsibilities

- Build prep packets with account summary, stakeholder map, security priorities, questions, and risks.
- Book Google Calendar meetings only after exported/current CRM target validation and suppression checks.
- Generate persisted prep packets from canonical account, contact, signal, event, and incident state.
- Record meeting outcomes and follow-up tasks, then sync them through provider-neutral `CrmClient` plans.
- Publish `meeting.booked`, `meeting.prep_packet_generated`, `meeting.outcome_recorded`, `meeting.follow_up_task_created`, and `crm.synced` events.

## Interfaces

- `POST /v1/calendar/availability`
- `POST /v1/meetings`
- `GET /v1/meetings`
- `GET /v1/meetings/{meeting_id}`
- `POST /v1/meetings/{meeting_id}/prep-packet`
- `POST /v1/meetings/{meeting_id}/outcome`
- `POST /v1/meetings/{meeting_id}/cancel`
- `POST /v1/meetings/{meeting_id}/retry-sync`
- `POST /v1/meetings/prep-packet`

## Failure Modes

- Missing contacts: generate account-only packet and flag gap.
- Missing signals: generate generic discovery questions.
- Unexported CRM target: reject meeting creation before any Google Calendar call.
- Suppressed attendee: reject meeting creation before any Google Calendar call.
- Google Calendar auth/rate-limit failure: fail the request with retryability; do not create duplicate meetings.
- CRM sync failure: retain outcome/task state and mark retryable or terminal sync status.

## Testing

- Packet generation tests.
- Missing-data fallback tests.
- Google Calendar adapter tests with fake/respx-backed provider responses.
- Meeting route, model, policy gate, sequence completion, and event contract tests.
- CRM sync retry tests for meeting outcomes and follow-up tasks.
