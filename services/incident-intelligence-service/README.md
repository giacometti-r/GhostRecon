# incident-intelligence-service

## Status

Sprint 5 runtime is implemented. The service uses the shared source registry and persists `NewsArticle`, `SecurityIncident`, `SecurityIncidentEvidence`, and `WatchTarget` records. It is registered in Helm and exposed through the gateway scaffold.

## Purpose

`incident-intelligence-service` discovers global cyber-incident reporting, identifies candidate affected companies, groups evidence into canonical incident cases, and manages company/domain/incident/event-series/topic watch targets.

It does not archive unlicensed full articles, treat discovery as corroboration by itself, collect breached personal data, approve CRM export, or enroll outreach.

## Sources

- GDELT DOC 2.0 global discovery using Article List JSON responses.
- Trusted publisher RSS/Atom feeds.
- Government, regulator, and CERT advisories.
- Configurable company, domain, incident, event-series, and topic queries through source definitions and watch targets.

## Runtime

```bash
GHOSTRECON_SERVICE_NAME=incident-intelligence-service \
uvicorn ghostrecon.service_apps.runtime:app --reload
```

Worker tasks:

- `ghostrecon.fetch_incident_source`
- `ghostrecon.parse_pending_incident_items`

## APIs

- `GET /v1/intelligence/incidents`
- `GET /v1/intelligence/incidents/{incident_id}`
- `POST /v1/intelligence/watch-targets`
- `GET /v1/intelligence/watch-targets`
- `PATCH /v1/intelligence/watch-targets/{watch_target_id}`
- `POST /v1/intelligence/incidents/{incident_id}/promote-to-watchlist`
- `GET /v1/intelligence/sources/health?kind=incident`

Mutating watchlist APIs require `Idempotency-Key` and actor context through the current scaffold header convention.

## Operator Rules

- Every incident starts as `candidate`.
- Corroborate only through authoritative disclosure, independent-source threshold, or Sprint 7 audited analyst decision.
- Treat syndicated copies and shared upstream reports as one evidence family.
- Promotion creates a watch target linked to the originating incident; it does not duplicate or auto-corroborate the case.
- Store article metadata and permitted excerpts, not unlicensed full text.
- Limit follow-on contact discovery to implemented public business roles in security, IT, risk, and communications.

## Health and Metrics

`GET /v1/intelligence/sources/health?kind=incident` exposes registered incident-source freshness, policy state, checkpoints, failures, and last-error metadata through the shared source registry. Also monitor article and syndication dedupe, language coverage, unresolved-company rate, incident candidate/corroboration rate, false-positive rate, watch-target lag, and reporting projection lag as later projections ship.

Recovery procedures are in `docs/runbooks/operations.md`.

## Related Specifications

- `docs/specifications/intelligence-pipeline.md`
- `docs/specifications/dashboard.md`
- `services/incident-intelligence-service/TECHNICAL_README.md`
