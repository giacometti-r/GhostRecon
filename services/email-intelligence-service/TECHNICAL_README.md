
# email-intelligence-service Technical README

## Architecture

Email Intelligence Service is implemented by `src/ghostrecon/services/email_candidates.py`, `src/ghostrecon/services/email_verifier.py`. It is exposed through `email_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

Related/shared modules referenced by this service: `src/ghostrecon/services/enrichment_workflows/`.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | `POST` | `/v1/email/candidates` | `email_candidates` |
| service | `POST` | `/v1/email/candidates/persist` | `email_persist_candidates` |
| service | `POST` | `/v1/email/verify-batch` | `email_verify_batch` |
| service | `POST` | `/v1/email/verify` | `email_verify` |
| gateway | `POST` | `/v1/email/candidates/persist` | `email_persist_candidates` |
| gateway | `POST` | `/v1/email/verify-batch` | `email_verify_batch` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.
- Generated email candidates carry `email` and `pattern` only; verifier status and payload are the supported quality signal after generation.

## Function Reference

### `src/ghostrecon/services/email_candidates.py`

#### Module Functions

##### `generate_email_candidates(full_name: str, domain: str, known_patterns: list[str] | None = None) -> list[EmailCandidate]`

- Inputs: `full_name` (str), `domain` (str), `known_patterns` (list[str] | None)
- Output: Returns `list[EmailCandidate]`.
- Why: `generate_email_candidates` provides the src/ghostrecon/services/email_candidates.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_name_parts`, `candidates.values`, `pattern.format`, `EmailCandidate`, `re.sub`, `local.lower`, `domain.lower`; uses parsing/normalization and deterministic generation order.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_name_parts(full_name: str) -> list[str]`

- Inputs: `full_name` (str)
- Output: Returns `list[str]`.
- Why: `_name_parts` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `unicodedata.normalize`, `decode`, `part.lower`, `normalized.encode`, `re.findall`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

### `src/ghostrecon/services/email_verifier.py`

#### Classes

##### `EmailVerifierClient`

`EmailVerifierClient` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `__init__(settings: Settings) -> None`
  - Inputs: `settings` (Settings)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes EmailVerifierClient with the provider, settings, or client state needed by later calls.
  - How: It calls `rstrip`.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.
- `async validate(email: EmailStr) -> dict[str, Any]`
  - Inputs: `email` (EmailStr)
  - Output: Returns `dict[str, Any]`.
  - Why: `EmailVerifierClient.validate` provides the src/ghostrecon/services/email_verifier.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `httpx.AsyncClient`, `response.raise_for_status`, `response.json`, `client.post`; uses HTTP/provider IO.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async validate_batch(emails: Sequence[EmailStr]) -> dict[str, Any]`
  - Inputs: `emails` (Sequence[EmailStr])
  - Output: Returns `dict[str, Any]`.
  - Why: `EmailVerifierClient.validate_batch` provides the src/ghostrecon/services/email_verifier.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `httpx.AsyncClient`, `response.raise_for_status`, `response.json`, `client.post`; uses HTTP/provider IO.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

## Shared Module Notes

- `src/ghostrecon/services/enrichment_workflows/` is shared or mounted behavior used by this service; its exhaustive function reference lives in the service that owns that module in the mapping, or in `gateway-service` for route/factory code.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_email_candidates.py`
- `tests/unit/test_enrichment_workflows.py`

## Shared Sprint 25a Security Perimeter

This service inherits correlation, transport bounds, security response headers, and strict-profile
reserved-header rejection from `create_base_app`. These behaviors are not owner-service
authentication or authorization. Direct-service restrictions, workload/OBO verification, complete
operation classification, database context installation, and active RLS remain Sprint 25b work. See
the [security foundation reference](../../docs/security-foundation.md).

## Startup and dependency contract

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns database and the HTTP email verifier. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Database-owning APIs verify the migrated schema; configured provider checks are named without exposing credentials.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
