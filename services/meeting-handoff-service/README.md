# meeting-handoff-service

## Purpose

`meeting-handoff-service` creates AE/SE prep packets, meeting context, and follow-up handoff artifacts from canonical account, contact, signal, and opportunity state.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=meeting-handoff-service`

## Dependencies

- CRM service for account/opportunity data.
- Calendar adapter in future sprints.
- Reporting service for meeting KPIs.

## Operations

- Generate packets quickly after meeting booked events.
- Keep source lineage so AE/SE users can validate claims.
- Monitor meeting-to-packet latency and packet generation failures.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=meeting-handoff-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
