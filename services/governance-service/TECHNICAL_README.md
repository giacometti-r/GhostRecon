
# governance-service Technical README

## Architecture

Governance Service is implemented by `src/ghostrecon/services/governance/`. It is exposed through `governance_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | `POST` | `/v1/suppressions` | `suppression_create` |
| service | `POST` | `/v1/suppressions/evaluate` | `suppression_check` |
| service | `GET` | `/v1/review/candidates` | `review_candidates` |
| service | `POST` | `/v1/review/candidates/{candidate_id}/approve` | `review_candidate_approve` |
| service | `POST` | `/v1/review/candidates/{candidate_id}/reject` | `review_candidate_reject` |
| service | `POST` | `/v1/review/candidates/bulk-decision` | `review_candidates_bulk_decision` |
| service | `GET` | `/v1/review/crm-targets` | `review_crm_targets` |
| service | `POST` | `/v1/governance/incidents/{incident_id}/corroborate` | `governance_corroborate_incident` |
| service | `POST` | `/v1/governance/incidents/{incident_id}/reject` | `governance_reject_incident` |
| service | `POST` | `/v1/governance/incidents/{incident_id}/revert` | `governance_revert_incident` |
| gateway | `POST` | `/v1/suppressions` | `suppression_create` |
| gateway | `POST` | `/v1/suppressions/evaluate` | `suppression_check` |
| gateway | `GET` | `/v1/review/candidates` | `review_candidates` |
| gateway | `POST` | `/v1/review/candidates/{candidate_id}/approve` | `review_candidate_approve` |
| gateway | `POST` | `/v1/review/candidates/{candidate_id}/reject` | `review_candidate_reject` |
| gateway | `POST` | `/v1/review/candidates/bulk-decision` | `review_candidates_bulk_decision` |
| gateway | `GET` | `/v1/review/crm-targets` | `review_crm_targets` |
| gateway | `POST` | `/v1/governance/incidents/{incident_id}/corroborate` | `governance_corroborate_incident` |
| gateway | `POST` | `/v1/governance/incidents/{incident_id}/reject` | `governance_reject_incident` |
| gateway | `POST` | `/v1/governance/incidents/{incident_id}/revert` | `governance_revert_incident` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.
- Incident decisions are optimistic-version aware; `revert_incident` is limited to `corroborated` incidents and returns them to `candidate`.

## Function Reference

### `src/ghostrecon/services/governance/`

#### Module Functions

##### `evaluate_suppression(request: SuppressionCheckRequest) -> SuppressionCheckResult`

- Inputs: `request` (SuppressionCheckRequest)
- Output: Returns `SuppressionCheckResult`.
- Why: `evaluate_suppression` applies policy or scoring rules and returns a decision object.
- How: It calls `SuppressionCheckResult`, `lower`, `split`; uses parsing/normalization, policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async evaluate_suppression_with_store(request: SuppressionCheckRequest, *, settings: Settings | None = None) -> SuppressionCheckResult`

- Inputs: `request` (SuppressionCheckRequest), `settings` (Settings | None)
- Output: Returns `SuppressionCheckResult`.
- Why: `evaluate_suppression_with_store` applies policy or scoring rules and returns a decision object.
- How: It calls `evaluate_suppression`, `matches.append`, `session_scope`, `SuppressionCheckResult`, `session.scalar`, `lower`, `limit`, `where`; uses database session queries, parsing/normalization, policy validation, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async create_suppression(request: SuppressionCreate, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> Suppression`

- Inputs: `request` (SuppressionCreate), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `Suppression`.
- Why: `create_suppression` creates and persists a new domain object while enforcing idempotency and policy.
- How: It calls `session_scope`, `Suppression`, `session.add`, `_audit`, `_enqueue_event`, `session.scalar`, `session.flush`, `new_event`; uses database session queries, database writes, idempotency lookup, outbox/event emission, parsing/normalization, policy validation, serialization/projection.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async approve_review_candidate(candidate_id: str, request: ReviewDecisionRequest, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> ReviewDecision | None`

- Inputs: `candidate_id` (str), `request` (ReviewDecisionRequest), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `ReviewDecision | None`; callers must handle the documented not-found or unavailable path.
- Why: `approve_review_candidate` provides the src/ghostrecon/services/governance/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `session_scope`, `_existing_decision`, `session.get`, `_approve_review_candidate_in_session`; uses database session queries, idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async reject_review_candidate(candidate_id: str, request: ReviewDecisionRequest, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> ReviewDecision | None`

- Inputs: `candidate_id` (str), `request` (ReviewDecisionRequest), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `ReviewDecision | None`; callers must handle the documented not-found or unavailable path.
- Why: `reject_review_candidate` provides the src/ghostrecon/services/governance/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `session_scope`, `_existing_decision`, `session.get`, `_reject_review_candidate_in_session`; uses database session queries, idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async bulk_decide_review_candidates(request: BulkReviewDecisionRequest, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> list[ReviewDecision]`

- Inputs: `request` (BulkReviewDecisionRequest), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `list[ReviewDecision]`.
- Why: `bulk_decide_review_candidates` provides the src/ghostrecon/services/governance/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `session_scope`, `any`, `all`, `ValueError`, `current_policy_hash`, `get`, `ReviewDecisionRequest`, `_existing_decision`; uses database session queries, idempotency lookup, policy validation.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`.

##### `async list_crm_targets(*, status: str | None = None, target_type: str | None = None, limit: int = 100, settings: Settings | None = None) -> list[CrmTarget]`

- Inputs: `status` (str | None), `target_type` (str | None), `limit` (int), `settings` (Settings | None)
- Output: Returns `list[CrmTarget]`.
- Why: `list_crm_targets` retrieves a bounded collection for API or workflow callers.
- How: It calls `session_scope`, `limit`, `stmt.where`, `all`, `order_by`, `desc`, `select`, `session.scalars`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async corroborate_incident(incident_id: str, request: IncidentDecisionRequest, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> ReviewDecision | None`

- Inputs: `incident_id` (str), `request` (IncidentDecisionRequest), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `ReviewDecision | None`; callers must handle the documented not-found or unavailable path.
- Why: `corroborate_incident` provides the src/ghostrecon/services/governance/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `session_scope`, `_create_decision`, `_audit`, `_enqueue_event`, `_existing_decision`, `session.get`, `ValueError`, `session.flush`; uses database session queries, database writes, idempotency lookup, outbox/event emission, policy validation, serialization/projection.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`; may return `None` for not-found or unavailable data.

##### `async reject_incident(incident_id: str, request: IncidentDecisionRequest, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> ReviewDecision | None`

- Inputs: `incident_id` (str), `request` (IncidentDecisionRequest), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `ReviewDecision | None`; callers must handle the documented not-found or unavailable path.
- Why: `reject_incident` provides the src/ghostrecon/services/governance/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `session_scope`, `_create_decision`, `_audit`, `_enqueue_event`, `_existing_decision`, `session.get`, `ValueError`, `session.flush`; uses database session queries, database writes, idempotency lookup, outbox/event emission, policy validation, serialization/projection.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`; may return `None` for not-found or unavailable data.

##### `current_policy_hash(candidate: ReviewCandidate) -> str`

- Inputs: `candidate` (ReviewCandidate)
- Output: Returns `str`.
- Why: `current_policy_hash` provides the src/ghostrecon/services/governance/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `policy_snapshot_hash`; uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `review_policy_blockers(candidate: ReviewCandidate) -> list[str]`

- Inputs: `candidate` (ReviewCandidate)
- Output: Returns `list[str]`.
- Why: `review_policy_blockers` provides the src/ghostrecon/services/governance/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `lower`, `blockers.append`, `snapshot.get`; uses parsing/normalization, policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `review_decision_to_api(decision: ReviewDecision) -> dict[str, object]`

- Inputs: `decision` (ReviewDecision)
- Output: Returns `dict[str, object]`.
- Why: `review_decision_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `review_decision_to_model(decision: ReviewDecision) -> ReviewDecisionOut`

- Inputs: `decision` (ReviewDecision)
- Output: Returns `ReviewDecisionOut`.
- Why: `review_decision_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `ReviewDecisionOut.model_validate`, `review_decision_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `crm_target_to_api(target: CrmTarget) -> dict[str, object]`

- Inputs: `target` (CrmTarget)
- Output: Returns `dict[str, object]`.
- Why: `crm_target_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `crm_target_to_model(target: CrmTarget) -> CrmTargetOut`

- Inputs: `target` (CrmTarget)
- Output: Returns `CrmTargetOut`.
- Why: `crm_target_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `CrmTargetOut.model_validate`, `crm_target_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `crm_targets_to_model(targets: list[CrmTarget]) -> CrmTargetList`

- Inputs: `targets` (list[CrmTarget])
- Output: Returns `CrmTargetList`.
- Why: `crm_targets_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `CrmTargetList`, `crm_target_to_model`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `suppression_to_api(suppression: Suppression) -> dict[str, object]`

- Inputs: `suppression` (Suppression)
- Output: Returns `dict[str, object]`.
- Why: `suppression_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `suppression_to_model(suppression: Suppression) -> SuppressionOut`

- Inputs: `suppression` (Suppression)
- Output: Returns `SuppressionOut`.
- Why: `suppression_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `SuppressionOut.model_validate`, `suppression_to_api`; uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _approve_review_candidate_in_session(session: Any, candidate: ReviewCandidate, request: ReviewDecisionRequest, *, actor: str, idempotency_key: str) -> ReviewDecision`

- Inputs: `session` (Any), `candidate` (ReviewCandidate), `request` (ReviewDecisionRequest), `actor` (str), `idempotency_key` (str)
- Output: Returns `ReviewDecision`.
- Why: `_approve_review_candidate_in_session` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_validate_candidate_decision`, `review_policy_blockers`, `_create_decision`, `_audit`, `_enqueue_event`, `_create_crm_target`, `ValueError`, `session.flush`; uses database writes, idempotency lookup, outbox/event emission, policy validation, serialization/projection.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`.

##### `async _reject_review_candidate_in_session(session: Any, candidate: ReviewCandidate, request: ReviewDecisionRequest, *, actor: str, idempotency_key: str) -> ReviewDecision`

- Inputs: `session` (Any), `candidate` (ReviewCandidate), `request` (ReviewDecisionRequest), `actor` (str), `idempotency_key` (str)
- Output: Returns `ReviewDecision`.
- Why: `_reject_review_candidate_in_session` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_validate_candidate_decision`, `_create_decision`, `_audit`, `_enqueue_event`, `session.flush`, `new_event`, `review_decision_to_api`; uses database writes, idempotency lookup, outbox/event emission, policy validation, serialization/projection.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_validate_candidate_decision(candidate: ReviewCandidate, request: ReviewDecisionRequest) -> None`

- Inputs: `candidate` (ReviewCandidate), `request` (ReviewDecisionRequest)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_validate_candidate_decision` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `ValueError`, `current_policy_hash`; uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `ValueError`; may return `None` for not-found or unavailable data.

##### `_create_decision(session: Any, *, review_candidate: ReviewCandidate | None, target_type: str, target_id: str, decision: str, actor: str, reason_code: str, reason: str | None, evidence_snapshot: dict[str, object], policy_snapshot: dict[str, object], idempotency_key: str) -> ReviewDecision`

- Inputs: `session` (Any), `review_candidate` (ReviewCandidate | None), `target_type` (str), `target_id` (str), `decision` (str), `actor` (str), `reason_code` (str), `reason` (str | None), `evidence_snapshot` (dict[str, object]), `policy_snapshot` (dict[str, object]), `idempotency_key` (str)
- Output: Returns `ReviewDecision`.
- Why: `_create_decision` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `ReviewDecision`, `session.add`, `_json_safe`, `policy_snapshot_hash`; uses database writes, idempotency lookup, policy validation.
- Side effects: mutates database state.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_create_crm_target(session: Any, candidate: ReviewCandidate, decision: ReviewDecision) -> CrmTarget`

- Inputs: `session` (Any), `candidate` (ReviewCandidate), `decision` (ReviewDecision)
- Output: Returns `CrmTarget`.
- Why: `_create_crm_target` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `CrmTarget`, `session.add`, `_json_safe`, `isoformat`; uses database writes, idempotency lookup, policy validation.
- Side effects: mutates database state.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _existing_decision(session: Any, idempotency_key: str) -> ReviewDecision | None`

- Inputs: `session` (Any), `idempotency_key` (str)
- Output: Returns `ReviewDecision | None`; callers must handle the documented not-found or unavailable path.
- Why: `_existing_decision` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session.scalar`, `where`, `select`; uses database session queries, idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `_audit(session: Any, actor: str, action: str, entity_type: str, entity_id: str, *, idempotency_key: str, payload: dict[str, object]) -> None`

- Inputs: `session` (Any), `actor` (str), `action` (str), `entity_type` (str), `entity_id` (str), `idempotency_key` (str), `payload` (dict[str, object])
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_audit` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session.add`, `AuditEvent`, `_json_safe`; uses database writes, idempotency lookup.
- Side effects: mutates database state.
- Failures: may return `None` for not-found or unavailable data.

##### `_enqueue_event(session: Any, event: Any) -> OutboxEvent`

- Inputs: `session` (Any), `event` (Any)
- Output: Returns `OutboxEvent`.
- Why: `_enqueue_event` creates an outbox event record for asynchronous consumers.
- How: It calls `event.model_dump`, `OutboxEvent`, `session.add`; uses database writes, idempotency lookup, outbox/event emission, serialization/projection.
- Side effects: mutates database state; adds outbox/event records.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_json_safe(value: object) -> object`

- Inputs: `value` (object)
- Output: Returns `object`.
- Why: `_json_safe` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `isinstance`, `value.isoformat`, `_json_safe`, `value.items`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_governance.py`

## Shared Sprint 25a Security Perimeter

This service inherits correlation, transport bounds, security response headers, and strict-profile
reserved-header rejection from `create_base_app`. These behaviors are not owner-service
authentication or authorization. Direct-service restrictions, workload/OBO verification, complete
operation classification, database context installation, and active RLS remain Sprint 25b work. See
the [security foundation reference](../../docs/security-foundation.md).

## Startup and dependency contract

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns database only. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Database-owning APIs verify the migrated schema; configured provider checks are named without exposing credentials.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
