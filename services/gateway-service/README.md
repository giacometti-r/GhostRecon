# gateway-service

## Purpose

`gateway-service` is the authenticated API entrypoint for GhostRecon. It exposes a stable route map for intelligence search, watchlists, review, reporting, CRM exports, and existing workflow services while keeping business logic in feature services.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=gateway-service`
- Health: `/healthz`
- Readiness: `/readyz`
- Metrics: `/metrics`

## Target Route Families

- `/v1/intelligence/events`, `/participants`, `/incidents`, `/watch-targets`, and `/sources/health`.
- `/v1/review/candidates` and `/review/crm-targets`.
- `/v1/crm/exports`.
- `/v1/reporting/*` and `/v1/kpis/catalog`.
- Existing enrichment, email, scoring, governance, sequencing, and handoff APIs.

## Dependencies

- Identity/role provider and trusted ingress/session boundary.
- Internal service discovery for feature and reporting services.
- Redis for distributed rate limits and short-lived request/operation state.
- PostgreSQL only where gateway-owned audit/auth state is explicitly required.

## Operations

- Terminate TLS at ingress/service mesh and enforce authentication before non-health routes.
- Authorize route/action scopes server-side; feature services re-authorize mutations.
- Preserve correlation and idempotency headers across downstream calls.
- Apply source/provider-aware request limits without hiding downstream `Retry-After`.
- Monitor 5xx, p95 latency, auth failures, policy denials, request size, and downstream timeouts.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=gateway-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
