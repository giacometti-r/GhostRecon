# enrichment-service

## Purpose

`enrichment-service` resolves companies/domains and collects permitted public business context for event and incident intelligence. It uses bounded company-page crawling, DNS/MX metadata, and public cybersecurity feeds such as CISA KEV and NVD without requiring paid enrichment APIs.

For incident work, contact discovery is limited to public security, IT, risk, and communications roles. Event participant contact enrichment is allowed only when the originating source explicitly permits reuse. Breached personal data is prohibited.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=enrichment-service`
- Crawler env: `GHOSTRECON_CRAWL_USER_AGENT`, `GHOSTRECON_CRAWL_RESPECT_ROBOTS`

## Dependencies

- Canonical event/participant/incident/company candidates and source-policy state.
- Public allowlisted company websites and DNS.
- CISA KEV feed and NVD CVE API.
- Governance service for reuse, retention, and eligibility policy.
- PostgreSQL/Redis for job, lineage, resolution, and retry state.

## Operations

- Keep crawling allowlisted, robots-aware, depth/page/rate limited, and source-attributed.
- Do not bypass authentication, CAPTCHAs, paywalls, or platform restrictions.
- Fail closed on participant permission ambiguity and reject breached-data input.
- Preserve entity-resolution alternatives and require review for ambiguous company/domain matches.
- Monitor crawl failure, resolution yield/corrections, pages fetched, contact eligibility, and policy-block rate.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=enrichment-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
