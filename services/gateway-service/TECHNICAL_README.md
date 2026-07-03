# gateway-service Technical README

## Responsibilities

- Publish the service map and aggregate OpenAPI discovery where appropriate.
- Route intelligence, review, CRM export, reporting, and existing workflow APIs to owning services.
- Own cross-cutting authentication, coarse authorization, correlation IDs, idempotency propagation, request limits, and response/error shape.
- Avoid business logic, canonical data ownership, policy decisions, and reporting projections.

## Interfaces

- `GET /v1/service-map`
- Standard endpoints: `/healthz`, `/readyz`, `/metrics`, `/docs`, `/openapi.json`
- Target route families are defined in `docs/specifications/intelligence-pipeline.md` and `docs/specifications/dashboard.md`.

## Request Rules

- Preserve `Authorization`, correlation ID, `Idempotency-Key`, actor/role context, and trace headers through trusted internal calls.
- Reject missing idempotency keys on designated mutations before forwarding.
- Enforce maximum query/date windows, page sizes, bulk-action counts, and body sizes.
- Return typed downstream errors with correlation/audit IDs; do not retry non-idempotent mutations automatically.
- Strip internal-only source payload fields and credentials from responses.

## Failure Modes

- Downstream unavailable: return typed degraded-service error with safe retry guidance.
- Authentication/authorization misconfigured: fail closed.
- Partial reporting degradation: preserve stale/degraded metadata rather than returning false empty success.
- Excess volume: apply gateway/ingress rate limits and bounded queues.
- Contract version mismatch: reject incompatible request/response and alert maintainers.

## Testing

- Service-map and route-contract tests including implemented event and incident intelligence services.
- Auth/role and feature-service re-authorization integration tests.
- Correlation/idempotency propagation and mutation retry-safety tests.
- Bulk/date/page/body limit tests.
- Downstream timeout, degraded reporting, and typed error tests.

## Scaling

Scale by stateless replicas. No sticky sessions are required; console session behavior remains outside this API boundary.
