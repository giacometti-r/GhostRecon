
# enrichment-service

## Purpose

Resolves organizations and contact candidates, enriches domains, verifies candidate email records, and performs bounded company-page crawling. It owns entity resolution, contact enrichment, domain enrichment, and crawler policy and should remain aligned with the implementation modules listed below.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=enrichment-service`
- App construction: `ghostrecon.service_apps.factory.build_app` selects the router by service name.
- Health, middleware, and common settings come from the shared base app.

## Implementation Modules

- `src/ghostrecon/services/enrichment.py`
- `src/ghostrecon/services/enrichment_workflows/`
- `src/ghostrecon/services/company_crawler.py`

## APIs And Jobs

- `POST /v1/enrichment/domain` via `domain_enrichment` (service router).
- `POST /v1/enrichment/entity-resolutions` via `enrichment_create_entity_resolution` (service router).
- `GET /v1/enrichment/entity-resolutions` via `enrichment_entity_resolutions` (service router).
- `POST /v1/enrichment/contact-candidates` via `enrichment_create_contact_candidate` (service router).
- `GET /v1/enrichment/contact-candidates` via `enrichment_contact_candidates` (service router).
- `POST /v1/enrichment/event-participants/{participant_id}/enrich-target` via `enrichment_event_participant_enrich_target` (service router).
- `POST /v1/enrichment/entity-resolutions` via `enrichment_create_entity_resolution` (gateway).
- `GET /v1/enrichment/entity-resolutions` via `enrichment_entity_resolutions` (gateway).
- `POST /v1/enrichment/contact-candidates` via `enrichment_create_contact_candidate` (gateway).
- `GET /v1/enrichment/contact-candidates` via `enrichment_contact_candidates` (gateway).
- `POST /v1/enrichment/event-participants/{participant_id}/enrich-target` via `enrichment_event_participant_enrich_target` (gateway).
- Worker/helper entrypoint: `ghostrecon.crawl_company_domain`.
- Worker/helper entrypoint: `ghostrecon.resolve_entity`.
- Worker/helper entrypoint: `ghostrecon.enrich_contact_candidate`.

## Dependencies

- DNS resolver.
- public HTTP titles.
- database sessions.
- review queue records.

## Shared Sprint 25a Security Perimeter

This FastAPI service inherits the shared transport perimeter: correlation IDs, declared
body/header/query bounds, security response headers, and strict-profile rejection of legacy identity
or untrusted internal security headers. This is not owner-service authentication or route
authorization. Direct service access, workload verification, OBO enforcement, complete operation
classification, and active RLS remain Sprint 25b work. See the [security foundation
reference](../../docs/security-foundation.md).

## Operations

- Treat idempotency headers as required where route handlers declare `Idempotency-Key`.
- Preserve policy, lineage, and audit fields when backfilling or replaying data.
- Use service-specific routes for isolated deployment and gateway routes for aggregate API access.
- Prefer fixtures and fake adapters in local development; live providers should be explicit environment configuration.
- Contact candidate listing supports `origin_id` alongside `origin_type` so event detail pages can detect already queued participant enrichment durably.

## Failure Modes

- Invalid or conflicting workflow requests are surfaced as `409` or validation errors by route handlers.
- Missing records are surfaced as `404` on detail/action endpoints.
- Provider outages should degrade or retry according to the service implementation rather than bypassing policy gates.
- Database or outbox failures leave the operation incomplete and should be retried with the same idempotency key when available.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=enrichment-service uvicorn ghostrecon.service_apps.runtime:app --reload --port 8080
```

## Verification

```bash
pytest tests/unit/test_enrichment_routes.py tests/unit/test_enrichment_workflows.py
```

## Runtime configuration

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns database; live OpenSERP search, HTTP email verifier, and identifying crawler user agent. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Database-owning APIs verify the migrated schema; configured provider checks are named without exposing credentials.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
