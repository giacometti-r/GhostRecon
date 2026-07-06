# enrichment-service Technical README

## Responsibilities

- Resolve event organizers/participants and incident affected-company candidates against canonical accounts/domains.
- Enrich accounts with domain metadata, MX, nameservers, website title, and public security signals.
- Run bounded Scrapy crawls against visible allowlisted company pages.
- Extract eligible public-business-contact facts with source URLs, role scope, confidence, and source-policy lineage.
- Publish `account.enriched` and `contact.discovered` events with `cyber_event` or `security_incident` origin where applicable.

## Interfaces

- `POST /v1/enrichment/domain`
- `POST /v1/enrichment/entity-resolutions`
- `GET /v1/enrichment/entity-resolutions`
- `POST /v1/enrichment/contact-candidates`
- `GET /v1/enrichment/contact-candidates`
- Worker task: `ghostrecon.crawl_company_domain`
- Worker task: `ghostrecon.resolve_entity`
- Worker task: `ghostrecon.enrich_contact_candidate`

Target requests add canonical origin IDs, source-item IDs, source-reuse state, and requested role scope. Requests missing required policy context fail closed.

## Entity and Contact Rules

- Resolve by normalized domain and supported organization identifiers before fuzzy names.
- Preserve alternatives/confidence for ambiguous organizations, subsidiaries, and similarly named companies.
- Event participant enrichment requires explicit `allowed` reuse for contact extraction.
- Incident contact roles are restricted to security, IT, risk, and communications business functions.
- Do not ingest breached datasets, private contact lists, authenticated pages, or name-only inferred identities.
- Every output retains source URL, retrieved time, origin event/incident, and policy version.

## Crawler Policy

- `ROBOTSTXT_OBEY` defaults to true.
- `AUTOTHROTTLE_ENABLED` defaults to true.
- Domain allowlisting is mandatory.
- Depth and page count are capped.

## Failure Modes

- DNS timeout/website unavailable: return partial enrichment and retain job state.
- Robots disallow: skip and record reason.
- Permission unknown/prohibited: reject contact extraction and emit a policy-block audit signal.
- Entity ambiguity: preserve candidates and route to analyst review.
- Missing lineage, prohibited participant reuse, out-of-scope incident roles, and breached-data provenance: block enrichment and create a review-visible record where appropriate.
- Feed outage: retry with backoff and retain last successful version/freshness state.
- Suspected breached data: quarantine metadata, do not persist payload, and alert governance.

## Testing

- Fixture-site Scrapy, robots, allowlist, depth, and rate-limit tests.
- Domain/company/subsidiary resolution and ambiguity tests.
- Participant reuse and incident-role-scope enforcement tests.
- Breached-data rejection and lineage propagation tests.
- DNS fallback and CISA/NVD mapping tests.
