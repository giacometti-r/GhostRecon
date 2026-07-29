
# enrichment-service Technical README

## Architecture

Enrichment Service is implemented by `src/ghostrecon/services/enrichment.py`, `src/ghostrecon/services/enrichment_workflows/`, `src/ghostrecon/services/company_crawler.py`. It is exposed through `enrichment_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | `POST` | `/v1/enrichment/domain` | `domain_enrichment` |
| service | `POST` | `/v1/enrichment/entity-resolutions` | `enrichment_create_entity_resolution` |
| service | `GET` | `/v1/enrichment/entity-resolutions` | `enrichment_entity_resolutions` |
| service | `POST` | `/v1/enrichment/contact-candidates` | `enrichment_create_contact_candidate` |
| service | `GET` | `/v1/enrichment/contact-candidates` | `enrichment_contact_candidates` |
| service | `POST` | `/v1/enrichment/event-participants/{participant_id}/enrich-target` | `enrichment_event_participant_enrich_target` |
| gateway | `POST` | `/v1/enrichment/entity-resolutions` | `enrichment_create_entity_resolution` |
| gateway | `GET` | `/v1/enrichment/entity-resolutions` | `enrichment_entity_resolutions` |
| gateway | `POST` | `/v1/enrichment/contact-candidates` | `enrichment_create_contact_candidate` |
| gateway | `GET` | `/v1/enrichment/contact-candidates` | `enrichment_contact_candidates` |
| gateway | `POST` | `/v1/enrichment/event-participants/{participant_id}/enrich-target` | `enrichment_event_participant_enrich_target` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.
- Contact candidate listing accepts `origin_id` for durable event participant queue checks.

## Function Reference

### `src/ghostrecon/services/enrichment.py`

#### Module Functions

##### `async enrich_domain(domain: str, security_signals: Sequence[dict[str, object]] = ()) -> DomainEnrichmentResult`

- Inputs: `domain` (str), `security_signals` (Sequence[dict[str, object]])
- Output: Returns `DomainEnrichmentResult`.
- Why: `enrich_domain` provides the src/ghostrecon/services/enrichment.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `DomainEnrichmentResult`, `removeprefix`, `_resolve_records`, `_fetch_title`, `domain.lower`; uses parsing/normalization.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_resolve_records(domain: str, record_type: str) -> list[str]`

- Inputs: `domain` (str), `record_type` (str)
- Output: Returns `list[str]`.
- Why: `_resolve_records` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `resolve`, `rstrip`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `async _fetch_title(domain: str) -> str | None`

- Inputs: `domain` (str)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_fetch_title` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `text.lower`, `lower.find`, `join`, `httpx.AsyncClient`, `response.raise_for_status`, `split`, `client.get`; uses HTTP/provider IO, parsing/normalization.
- Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data; catches provider or validation errors and maps them to the module contract.

### `src/ghostrecon/services/enrichment_workflows/`

#### Classes

##### `EnrichmentWorkflowRepository`

`EnrichmentWorkflowRepository` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `__init__(session: AsyncSession) -> None`
  - Inputs: `session` (AsyncSession)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes EnrichmentWorkflowRepository with the provider, settings, or client state needed by later calls.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.
- `async create_entity_resolution(payload: EntityResolutionCreate, idempotency_key: str) -> EntityResolutionCase`
  - Inputs: `payload` (EntityResolutionCreate), `idempotency_key` (str)
  - Output: Returns `EntityResolutionCase`.
  - Why: `EnrichmentWorkflowRepository.create_entity_resolution` creates and persists a new domain object while enforcing idempotency and policy.
  - How: It calls `normalize_domain`, `EntityResolutionCase`, `add`, `scalar`, `flush`, `self._find_account_matches`, `_account_summary`, `self._enqueue_event`; uses database session queries, database writes, idempotency lookup, outbox/event emission, parsing/normalization, policy validation, serialization/projection.
  - Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async list_entity_resolutions(*, status: str | None, origin_type: str | None, limit: int) -> list[EntityResolutionCase]`
  - Inputs: `status` (str | None), `origin_type` (str | None), `limit` (int)
  - Output: Returns `list[EntityResolutionCase]`.
  - Why: `EnrichmentWorkflowRepository.list_entity_resolutions` retrieves a bounded collection for API or workflow callers.
  - How: It calls `limit`, `stmt.where`, `execute`, `result.scalars`, `order_by`, `desc`, `select`; uses database session queries.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async create_contact_candidate(payload: ContactEnrichmentCreate, idempotency_key: str) -> ContactEnrichmentCandidate`
  - Inputs: `payload` (ContactEnrichmentCreate), `idempotency_key` (str)
  - Output: Returns `ContactEnrichmentCandidate`.
  - Why: `EnrichmentWorkflowRepository.create_contact_candidate` creates and persists a new domain object while enforcing idempotency and policy.
  - How: It calls `evaluate_contact_policy`, `normalize_domain`, `ContactEnrichmentCandidate`, `add`, `scalar`, `flush`, `self._enqueue_event`, `where`; uses database session queries, database writes, idempotency lookup, outbox/event emission, parsing/normalization, policy validation, serialization/projection.
  - Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async list_contact_candidates(*, status: str | None, origin_type: str | None, limit: int) -> list[ContactEnrichmentCandidate]`
  - Inputs: `status` (str | None), `origin_type` (str | None), `limit` (int)
  - Output: Returns `list[ContactEnrichmentCandidate]`.
  - Why: `EnrichmentWorkflowRepository.list_contact_candidates` retrieves a bounded collection for API or workflow callers.
  - How: It calls `limit`, `stmt.where`, `execute`, `result.scalars`, `order_by`, `desc`, `select`; uses database session queries.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async persist_email_candidates(payload: EmailCandidatePersistRequest, idempotency_key: str) -> list[EmailCandidateRecord]`
  - Inputs: `payload` (EmailCandidatePersistRequest), `idempotency_key` (str)
  - Output: Returns `list[EmailCandidateRecord]`.
  - Why: `EnrichmentWorkflowRepository.persist_email_candidates` provides the src/ghostrecon/services/enrichment_workflows/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `generate_email_candidates`, `self._resolve_email_contact_context`, `ValueError`, `self._email_patterns`, `EmailCandidateRecord`, `add`, `self._enqueue_event`, `records.append`; uses database session queries, database writes, idempotency lookup, outbox/event emission, policy validation. Persisted records retain pattern and verification workflow fields, not pre-verification confidence.
  - Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
  - Failures: raises `ValueError`.
- `async verify_email_candidates(payload: EmailVerifyBatchRequest, verifier: EmailVerifierClient) -> list[EmailCandidateRecord]`
  - Inputs: `payload` (EmailVerifyBatchRequest), `verifier` (EmailVerifierClient)
  - Output: Returns `list[EmailCandidateRecord]`.
  - Why: `EnrichmentWorkflowRepository.verify_email_candidates` provides the src/ghostrecon/services/enrichment_workflows/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `execute`, `result.scalars`, `classify_verification_result`, `utcnow`, `where`, `self._fetch_verification_results`, `verification_results.get`, `self._enqueue_event`; uses database session queries, idempotency lookup, outbox/event emission, policy validation, serialization/projection, time calculations.
  - Side effects: adds outbox/event records; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async list_review_candidates(*, status: str | None, candidate_type: str | None, limit: int) -> list[ReviewCandidate]`
  - Inputs: `status` (str | None), `candidate_type` (str | None), `limit` (int)
  - Output: Returns `list[ReviewCandidate]`.
  - Why: `EnrichmentWorkflowRepository.list_review_candidates` retrieves a bounded collection for API or workflow callers.
  - How: It calls `limit`, `stmt.where`, `execute`, `result.scalars`, `order_by`, `desc`, `select`; uses database session queries.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async _find_account_matches(domain: str | None, organization_name: str | None) -> list[Account]`
  - Inputs: `domain` (str | None), `organization_name` (str | None)
  - Output: Returns `list[Account]`.
  - Why: `EnrichmentWorkflowRepository._find_account_matches` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `execute`, `result.scalars`, `limit`, `where`, `select`, `func.lower`, `domain.lower`, `organization_name.lower`; uses database session queries, parsing/normalization.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async _upsert_contact(candidate: ContactEnrichmentCandidate) -> Contact`
  - Inputs: `candidate` (ContactEnrichmentCandidate)
  - Output: Returns `Contact`.
  - Why: `EnrichmentWorkflowRepository._upsert_contact` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `Contact`, `add`, `scalar`, `flush`, `where`, `select`; uses database session queries, database writes, idempotency lookup, policy validation.
  - Side effects: mutates database state; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async _resolve_email_contact_context(payload: EmailCandidatePersistRequest) -> tuple[Contact, dict[str, Any]]`
  - Inputs: `payload` (EmailCandidatePersistRequest)
  - Output: Returns `tuple[Contact, dict[str, Any]]`.
  - Why: `EnrichmentWorkflowRepository._resolve_email_contact_context` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `ValueError`, `get`; uses database session queries, policy validation.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: raises `ValueError`.
- `async _email_patterns(domain: str, requested: list[str]) -> list[str] | None`
  - Inputs: `domain` (str), `requested` (list[str])
  - Output: Returns `list[str] | None`; callers must handle the documented not-found or unavailable path.
  - Why: `EnrichmentWorkflowRepository._email_patterns` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `normalize_domain`, `execute`, `limit`, `result.scalars`, `order_by`, `desc`, `where`, `select`; uses database session queries, parsing/normalization.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: may return `None` for not-found or unavailable data.
- `async _fetch_verification_results(records: list[EmailCandidateRecord], verifier: EmailVerifierClient) -> dict[str, dict[str, object]]`
  - Inputs: `records` (list[EmailCandidateRecord]), `verifier` (EmailVerifierClient)
  - Output: Returns `dict[str, dict[str, object]]`.
  - Why: `EnrichmentWorkflowRepository._fetch_verification_results` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `isinstance`, `verifier.validate_batch`, `response.get`, `item.get`.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async _upsert_email_pattern(record: EmailCandidateRecord) -> None`
  - Inputs: `record` (EmailCandidateRecord)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: `EnrichmentWorkflowRepository._upsert_email_pattern` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `lower`, `add`, `scalar`, `max`, `OrganizationEmailPattern`, `where`, `rsplit`, `select`; uses database session queries, database writes, idempotency lookup, parsing/normalization. Pattern confidence is derived from verified outcomes rather than copied from generated candidates.
  - Side effects: mutates database state; runs asynchronously and may await database or provider operations.
  - Failures: may return `None` for not-found or unavailable data.
- `async _request_review(*, candidate_type: str, target_type: str, target_id: str, origin_type: str | None, origin_id: str | None, source_definition_id: str | None, source_item_ids: list[object], reason_code: str, reason: str, evidence_summary: dict[str, object], policy_snapshot: dict[str, object]) -> ReviewCandidate`
  - Inputs: `candidate_type` (str), `target_type` (str), `target_id` (str), `origin_type` (str | None), `origin_id` (str | None), `source_definition_id` (str | None), `source_item_ids` (list[object]), `reason_code` (str), `reason` (str), `evidence_summary` (dict[str, object]), `policy_snapshot` (dict[str, object])
  - Output: Returns `ReviewCandidate`.
  - Why: `EnrichmentWorkflowRepository._request_review` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `ReviewCandidate`, `add`, `self._enqueue_event`, `scalar`, `flush`, `new_event`, `where`, `select`; uses database session queries, database writes, idempotency lookup, outbox/event emission, policy validation.
  - Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `_enqueue_event(event: Any) -> OutboxEvent`
  - Inputs: `event` (Any)
  - Output: Returns `OutboxEvent`.
  - Why: `EnrichmentWorkflowRepository._enqueue_event` creates an outbox event record for asynchronous consumers.
  - How: It calls `event.model_dump`, `OutboxEvent`, `add`; uses database writes, idempotency lookup, outbox/event emission, serialization/projection.
  - Side effects: mutates database state; adds outbox/event records.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

#### Module Functions

##### `utcnow() -> datetime`

- Inputs: No external inputs.
- Output: Returns `datetime`.
- Why: `utcnow` provides the src/ghostrecon/services/enrichment_workflows/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `datetime.now`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `normalize_domain(domain: str | None) -> str | None`

- Inputs: `domain` (str | None)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `normalize_domain` canonicalizes caller or provider input before comparison/persistence.
- How: It calls `removeprefix`, `cleaned.split`, `domain.lower`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `evaluate_contact_policy(payload: ContactEnrichmentCreate) -> tuple[str, str | None]`

- Inputs: `payload` (ContactEnrichmentCreate)
- Output: Returns `tuple[str, str | None]`; callers must handle the documented not-found or unavailable path.
- Why: `evaluate_contact_policy` applies policy or scoring rules and returns a decision object.
- How: It uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `classify_verification_result(result: dict[str, object]) -> tuple[str, str | None]`

- Inputs: `result` (dict[str, object])
- Output: Returns `tuple[str, str | None]`; callers must handle the documented not-found or unavailable path.
- Why: `classify_verification_result` maps raw state into an internal classification used by callers.
- How: It calls `lower`, `_truthy`, `result.get`; uses parsing/normalization, policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `async create_entity_resolution(payload: EntityResolutionCreate, *, idempotency_key: str, settings: Settings | None = None) -> EntityResolutionCase`

- Inputs: `payload` (EntityResolutionCreate), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `EntityResolutionCase`.
- Why: `create_entity_resolution` creates and persists a new domain object while enforcing idempotency and policy.
- How: It calls `session_scope`, `create_entity_resolution`, `EnrichmentWorkflowRepository`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async list_entity_resolutions(*, status: str | None = None, origin_type: str | None = None, limit: int = 100, settings: Settings | None = None) -> list[EntityResolutionCase]`

- Inputs: `status` (str | None), `origin_type` (str | None), `limit` (int), `settings` (Settings | None)
- Output: Returns `list[EntityResolutionCase]`.
- Why: `list_entity_resolutions` retrieves a bounded collection for API or workflow callers.
- How: It calls `session_scope`, `EnrichmentWorkflowRepository`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async create_contact_enrichment_candidate(payload: ContactEnrichmentCreate, *, idempotency_key: str, settings: Settings | None = None) -> ContactEnrichmentCandidate`

- Inputs: `payload` (ContactEnrichmentCreate), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `ContactEnrichmentCandidate`.
- Why: `create_contact_enrichment_candidate` creates and persists a new domain object while enforcing idempotency and policy.
- How: It calls `session_scope`, `create_contact_candidate`, `EnrichmentWorkflowRepository`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async list_contact_enrichment_candidates(*, status: str | None = None, origin_type: str | None = None, limit: int = 100, settings: Settings | None = None) -> list[ContactEnrichmentCandidate]`

- Inputs: `status` (str | None), `origin_type` (str | None), `limit` (int), `settings` (Settings | None)
- Output: Returns `list[ContactEnrichmentCandidate]`.
- Why: `list_contact_enrichment_candidates` retrieves a bounded collection for API or workflow callers.
- How: It calls `session_scope`, `EnrichmentWorkflowRepository`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async persist_email_candidates(payload: EmailCandidatePersistRequest, *, idempotency_key: str, settings: Settings | None = None) -> list[EmailCandidateRecord]`

- Inputs: `payload` (EmailCandidatePersistRequest), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `list[EmailCandidateRecord]`.
- Why: `persist_email_candidates` provides the src/ghostrecon/services/enrichment_workflows/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `session_scope`, `persist_email_candidates`, `EnrichmentWorkflowRepository`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async verify_email_candidates(payload: EmailVerifyBatchRequest, *, settings: Settings | None = None) -> list[EmailCandidateRecord]`

- Inputs: `payload` (EmailVerifyBatchRequest), `settings` (Settings | None)
- Output: Returns `list[EmailCandidateRecord]`.
- Why: `verify_email_candidates` provides the src/ghostrecon/services/enrichment_workflows/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `session_scope`, `EmailVerifierClient`, `verify_email_candidates`, `Settings`, `EnrichmentWorkflowRepository`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async list_review_candidates(*, status: str | None = 'open', candidate_type: str | None = None, limit: int = 100, settings: Settings | None = None) -> list[ReviewCandidate]`

- Inputs: `status` (str | None), `candidate_type` (str | None), `limit` (int), `settings` (Settings | None)
- Output: Returns `list[ReviewCandidate]`.
- Why: `list_review_candidates` retrieves a bounded collection for API or workflow callers.
- How: It calls `session_scope`, `EnrichmentWorkflowRepository`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `entity_resolution_to_api(case: EntityResolutionCase) -> dict[str, object]`

- Inputs: `case` (EntityResolutionCase)
- Output: Returns `dict[str, object]`.
- Why: `entity_resolution_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `contact_candidate_to_api(candidate: ContactEnrichmentCandidate) -> dict[str, object]`

- Inputs: `candidate` (ContactEnrichmentCandidate)
- Output: Returns `dict[str, object]`.
- Why: `contact_candidate_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `email_candidate_to_api(candidate: EmailCandidateRecord) -> dict[str, object]`

- Inputs: `candidate` (EmailCandidateRecord)
- Output: Returns `dict[str, object]`.
- Why: `email_candidate_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `review_candidate_to_api(candidate: ReviewCandidate) -> dict[str, object]`

- Inputs: `candidate` (ReviewCandidate)
- Output: Returns `dict[str, object]`.
- Why: `review_candidate_to_api` serializes a persisted ORM object into the API/model contract.
- How: It calls `getattr`; uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `entity_resolution_to_model(case: EntityResolutionCase) -> EntityResolutionOut`

- Inputs: `case` (EntityResolutionCase)
- Output: Returns `EntityResolutionOut`.
- Why: `entity_resolution_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `EntityResolutionOut.model_validate`, `entity_resolution_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `contact_candidate_to_model(candidate: ContactEnrichmentCandidate) -> ContactEnrichmentOut`

- Inputs: `candidate` (ContactEnrichmentCandidate)
- Output: Returns `ContactEnrichmentOut`.
- Why: `contact_candidate_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `ContactEnrichmentOut.model_validate`, `contact_candidate_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `email_candidate_to_model(candidate: EmailCandidateRecord) -> EmailCandidateRecordOut`

- Inputs: `candidate` (EmailCandidateRecord)
- Output: Returns `EmailCandidateRecordOut`.
- Why: `email_candidate_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `EmailCandidateRecordOut.model_validate`, `email_candidate_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `review_candidate_to_model(candidate: ReviewCandidate) -> ReviewCandidateOut`

- Inputs: `candidate` (ReviewCandidate)
- Output: Returns `ReviewCandidateOut`.
- Why: `review_candidate_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `ReviewCandidateOut.model_validate`, `review_candidate_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_truthy(result: dict[str, object], *keys: str) -> bool`

- Inputs: `result` (dict[str, object]), `*keys`
- Output: Returns `bool`.
- Why: `_truthy` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `any`, `bool`, `result.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_account_summary(account: Account) -> dict[str, object]`

- Inputs: `account` (Account)
- Output: Returns `dict[str, object]`.
- Why: `_account_summary` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

### `src/ghostrecon/services/company_crawler.py`

#### Classes

##### `DiscoveredContact`

`DiscoveredContact` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `full_name` (str | None), `title` (str | None), `email` (str | None), `source_url` (str), `confidence` (int).

##### `CompanyContactSpider`

`CompanyContactSpider` is a data container or runtime class based on `scrapy.Spider`. Fields: `name`.

- `__init__(*, domain: str, max_pages: int = 40, max_depth: int = 2, **kwargs: object) -> None`
  - Inputs: `domain` (str), `max_pages` (int), `max_depth` (int), `**kwargs`
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes CompanyContactSpider with the provider, settings, or client state needed by later calls.
  - How: It calls `__init__`, `domain.lower`, `LinkExtractor`, `super`; uses parsing/normalization, policy validation.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.
- `parse(response: scrapy.http.Response) -> Iterable[dict[str, object]]`
  - Inputs: `response` (scrapy.http.Response)
  - Output: Returns `Iterable[dict[str, object]]`.
  - Why: `CompanyContactSpider.parse` provides the src/ghostrecon/services/company_crawler.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `extract_links`, `self._extract_contacts`, `get`, `_is_promising_contact_url`, `response.follow`; uses parsing/normalization.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `_extract_contacts(response: scrapy.http.Response) -> Iterable[dict[str, object]]`
  - Inputs: `response` (scrapy.http.Response)
  - Output: Returns `Iterable[dict[str, object]]`.
  - Why: `CompanyContactSpider._extract_contacts` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `join`, `_extract_title_hint`, `getall`, `EMAIL_PATTERN.findall`, `response.css`, `DiscoveredContact`, `email.lower`; uses parsing/normalization.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

#### Module Functions

##### `build_scrapy_settings(user_agent: str, respect_robots: bool = True) -> ScrapySettings`

- Inputs: `user_agent` (str), `respect_robots` (bool)
- Output: Returns `ScrapySettings`.
- Why: `build_scrapy_settings` derives a stable request, key, or projection object from richer inputs.
- How: It calls `ScrapySettings`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `run_company_crawl(domain: str, user_agent: str, respect_robots: bool = True) -> None`

- Inputs: `domain` (str), `user_agent` (str), `respect_robots` (bool)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `run_company_crawl` provides the src/ghostrecon/services/company_crawler.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `CrawlerProcess`, `process.crawl`, `process.start`, `build_scrapy_settings`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_is_promising_contact_url(url: str) -> bool`

- Inputs: `url` (str)
- Output: Returns `bool`.
- Why: `_is_promising_contact_url` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `lower`, `any`, `urlparse`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_extract_title_hint(text: str) -> str | None`

- Inputs: `text` (str)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_extract_title_hint` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `CONTACT_TITLE_HINTS.search`, `match.group`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_enrichment_routes.py`
- `tests/unit/test_enrichment_workflows.py`

## Startup and dependency contract

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns database; live OpenSERP search, HTTP email verifier, and identifying crawler user agent. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Database-owning APIs verify the migrated schema; configured provider checks are named without exposing credentials.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
