
# scoring-routing-service Technical README

## Architecture

Scoring Routing Service is implemented by `src/ghostrecon/services/scoring.py`. It is exposed through `scoring_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | `POST` | `/v1/scoring/lead` | `lead_score` |
| service | `POST` | `/v1/scoring/candidates` | `candidate_score` |
| gateway | `POST` | `/v1/scoring/candidates` | `candidate_score` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.

## Function Reference

### `src/ghostrecon/services/scoring.py`

#### Module Functions

##### `score_lead(request: ScoreRequest) -> ScoreResult`

- Inputs: `request` (ScoreRequest)
- Output: Returns `ScoreResult`.
- Why: `score_lead` provides the src/ghostrecon/services/scoring.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `account.get`, `min`, `round`, `ScoreResult`, `reasons.append`, `signal.get`, `max`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `score_candidate_preview(request: CandidateScoreRequest) -> CandidateScoreOut`

- Inputs: `request` (CandidateScoreRequest)
- Output: Returns `CandidateScoreOut`.
- Why: `score_candidate_preview` provides the src/ghostrecon/services/scoring.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_component_scores`, `policy_blockers_for_score`, `round`, `_route_for_score`, `CandidateScoreOut`, `reasons.extend`, `reasons.append`, `policy_snapshot_hash`; uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async create_candidate_score(request: CandidateScoreRequest, *, idempotency_key: str, settings: Settings | None = None) -> CandidateScore`

- Inputs: `request` (CandidateScoreRequest), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `CandidateScore`.
- Why: `create_candidate_score` creates and persists a new domain object while enforcing idempotency and policy.
- How: It calls `session_scope`, `score_candidate_preview`, `CandidateScore`, `session.add`, `_enqueue_event`, `session.scalar`, `session.flush`, `new_event`; uses database session queries, database writes, idempotency lookup, outbox/event emission, policy validation, serialization/projection.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `candidate_score_to_api(score: CandidateScore) -> dict[str, object]`

- Inputs: `score` (CandidateScore)
- Output: Returns `dict[str, object]`.
- Why: `candidate_score_to_api` serializes a persisted ORM object into the API/model contract.
- How: It calls `components.get`; uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `candidate_score_to_model(score: CandidateScore) -> CandidateScoreOut`

- Inputs: `score` (CandidateScore)
- Output: Returns `CandidateScoreOut`.
- Why: `candidate_score_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `CandidateScoreOut.model_validate`, `candidate_score_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `policy_snapshot_hash(snapshot: dict[str, object]) -> str`

- Inputs: `snapshot` (dict[str, object])
- Output: Returns `str`.
- Why: `policy_snapshot_hash` provides the src/ghostrecon/services/scoring.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `json.dumps`, `hexdigest`, `hashlib.sha256`, `payload.encode`; uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `policy_blockers_for_score(request: CandidateScoreRequest) -> list[str]`

- Inputs: `request` (CandidateScoreRequest)
- Output: Returns `list[str]`.
- Why: `policy_blockers_for_score` provides the src/ghostrecon/services/scoring.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `lower`, `_optional_int`, `blockers.append`, `snapshot.get`, `get`; uses parsing/normalization, policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_component_scores(request: CandidateScoreRequest) -> tuple[dict[str, int], list[str]]`

- Inputs: `request` (CandidateScoreRequest)
- Output: Returns `tuple[dict[str, int], list[str]]`.
- Why: `_component_scores` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `account.get`, `max`, `_int_or_default`, `evidence.get`, `_optional_int`, `reasons.append`, `contact.get`, `min`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_route_for_score(score: int, policy_blockers: list[str]) -> CandidateScoreRoute`

- Inputs: `score` (int), `policy_blockers` (list[str])
- Output: Returns `CandidateScoreRoute`.
- Why: `_route_for_score` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _request_score_review(session: Any, request: CandidateScoreRequest, score: CandidateScore, preview: CandidateScoreOut) -> ReviewCandidate`

- Inputs: `session` (Any), `request` (CandidateScoreRequest), `score` (CandidateScore), `preview` (CandidateScoreOut)
- Output: Returns `ReviewCandidate`.
- Why: `_request_score_review` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `ReviewCandidate`, `session.add`, `_enqueue_event`, `session.scalar`, `session.flush`, `new_event`, `where`, `select`; uses database session queries, database writes, idempotency lookup, outbox/event emission, policy validation.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_enqueue_event(session: Any, event: Any) -> OutboxEvent`

- Inputs: `session` (Any), `event` (Any)
- Output: Returns `OutboxEvent`.
- Why: `_enqueue_event` creates an outbox event record for asynchronous consumers.
- How: It calls `event.model_dump`, `OutboxEvent`, `session.add`; uses database writes, idempotency lookup, outbox/event emission, serialization/projection.
- Side effects: mutates database state; adds outbox/event records.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_optional_int(value: object, default: int | None = None) -> int | None`

- Inputs: `value` (object), `default` (int | None)
- Output: Returns `int | None`; callers must handle the documented not-found or unavailable path.
- Why: `_optional_int` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data; catches provider or validation errors and maps them to the module contract.

##### `_int_or_default(value: object, default: int = 0) -> int`

- Inputs: `value` (object), `default` (int)
- Output: Returns `int`.
- Why: `_int_or_default` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_optional_int`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_clamp(value: int) -> int`

- Inputs: `value` (int)
- Output: Returns `int`.
- Why: `_clamp` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `min`, `max`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_scoring.py`
