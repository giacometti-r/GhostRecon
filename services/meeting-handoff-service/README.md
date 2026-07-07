# meeting-handoff-service

## Purpose

`meeting-handoff-service` creates Google Calendar meetings, AE/SE prep packets, meeting outcomes, and follow-up handoff artifacts from canonical account, contact, signal, CRM target, sequence, event, and incident state.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=meeting-handoff-service`
- Google env: `GHOSTRECON_GOOGLE_CALENDAR_ID`, `GHOSTRECON_GOOGLE_CLIENT_EMAIL`, `GHOSTRECON_GOOGLE_PRIVATE_KEY`, optional `GHOSTRECON_GOOGLE_DELEGATED_SUBJECT`, and `GHOSTRECON_GOOGLE_CALENDAR_SEND_UPDATES`.
- Local runs without Google credentials use the fake calendar adapter. Staging/prod should provide service-account credentials and calendar access.

## Dependencies

- CRM service for account/opportunity data.
- Google Calendar API for availability, event creation, and cancellation.
- Reporting service for meeting KPIs.
- Attio/`CrmClient` for meeting outcome and follow-up task sync.

## Operations

- Generate packets quickly after meeting booked events.
- Keep source lineage so AE/SE users can validate claims.
- Monitor Google auth failures, Calendar API rate limits, meeting-to-packet latency, packet generation failures, and CRM sync failures.
- Retry failed CRM handoff sync through `POST /v1/meetings/{meeting_id}/retry-sync` or the `ghostrecon.retry_meeting_crm_sync` task.

## Interfaces

- `POST /v1/calendar/availability`
- `POST /v1/meetings`
- `GET /v1/meetings`
- `GET /v1/meetings/{meeting_id}`
- `POST /v1/meetings/{meeting_id}/prep-packet`
- `POST /v1/meetings/{meeting_id}/outcome`
- `POST /v1/meetings/{meeting_id}/cancel`
- `POST /v1/meetings/{meeting_id}/retry-sync`
- `POST /v1/meetings/prep-packet` for stateless compatibility only.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=meeting-handoff-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
