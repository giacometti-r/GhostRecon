
# sequencing-service Technical README

## Architecture

Sequencing Service is implemented by `src/ghostrecon/services/sequencing/`, `src/ghostrecon/services/sequence_adapters.py`. It is exposed through `sequencing_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | `POST` | `/v1/sequences/evaluate` | `sequence_eligibility` |
| service | `POST` | `/v1/sequences` | `sequence_create` |
| service | `POST` | `/v1/sequences/enrollments` | `sequence_enrollment_create` |
| service | `GET` | `/v1/sequences/enrollments` | `sequence_enrollment_list` |
| service | `GET` | `/v1/sequences/enrollments/{enrollment_id}` | `sequence_enrollment_detail` |
| service | `POST` | `/v1/sequences/enrollments/{enrollment_id}/pause` | `sequence_enrollment_pause` |
| service | `POST` | `/v1/sequences/enrollments/{enrollment_id}/resume` | `sequence_enrollment_resume` |
| service | `POST` | `/v1/sequences/enrollments/{enrollment_id}/cancel` | `sequence_enrollment_cancel` |
| service | `POST` | `/v1/sequences/unsubscribe` | `sequence_unsubscribe` |
| gateway | `POST` | `/v1/sequences/evaluate` | `sequence_eligibility` |
| gateway | `POST` | `/v1/sequences` | `sequence_create` |
| gateway | `POST` | `/v1/sequences/enrollments` | `sequence_enrollment_create` |
| gateway | `GET` | `/v1/sequences/enrollments` | `sequence_enrollment_list` |
| gateway | `GET` | `/v1/sequences/enrollments/{enrollment_id}` | `sequence_enrollment_detail` |
| gateway | `POST` | `/v1/sequences/enrollments/{enrollment_id}/pause` | `sequence_enrollment_pause` |
| gateway | `POST` | `/v1/sequences/enrollments/{enrollment_id}/resume` | `sequence_enrollment_resume` |
| gateway | `POST` | `/v1/sequences/enrollments/{enrollment_id}/cancel` | `sequence_enrollment_cancel` |
| gateway | `POST` | `/v1/sequences/unsubscribe` | `sequence_unsubscribe` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.

## Function Reference

### `src/ghostrecon/services/sequencing/`

#### Classes

##### `_SafeFormat`

`_SafeFormat` is a data container or runtime class based on `dict[str, str]`. Fields: none declared at class level.

- `__missing__(key: str) -> str`
  - Inputs: `key` (str)
  - Output: Returns `str`.
  - Why: `_SafeFormat.__missing__` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

#### Module Functions

##### `evaluate_sequence_eligibility(request: SequenceEligibilityRequest) -> SequenceEligibilityResult`

- Inputs: `request` (SequenceEligibilityRequest)
- Output: Returns `SequenceEligibilityResult`.
- Why: `evaluate_sequence_eligibility` applies policy or scoring rules and returns a decision object.
- How: It calls `SequenceEligibilityResult`, `get`, `reasons.append`; uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async create_sequence(request: SequenceCreateRequest, *, actor: str, idempotency_key: str | None = None, settings: Settings | None = None) -> SequenceOut`

- Inputs: `request` (SequenceCreateRequest), `actor` (str), `idempotency_key` (str | None), `settings` (Settings | None)
- Output: Returns `SequenceOut`.
- Why: `create_sequence` creates and persists a new domain object while enforcing idempotency and policy.
- How: It calls `session_scope`, `utcnow`, `Sequence`, `session.add`, `enumerate`, `sequence_to_model`, `session.flush`, `SequenceStep`; uses database session queries, database writes, idempotency lookup, parsing/normalization, policy validation, serialization/projection, time calculations.
- Side effects: mutates database state; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async create_sequence_enrollment(request: SequenceEnrollmentCreateRequest, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> SequenceEnrollmentOut`

- Inputs: `request` (SequenceEnrollmentCreateRequest), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `SequenceEnrollmentOut`.
- Why: `create_sequence_enrollment` creates and persists a new domain object while enforcing idempotency and policy.
- How: It calls `ValueError`, `session_scope`, `_require_sendable_contact`, `_domain_from_email`, `utcnow`, `policy_snapshot.update`, `SequenceEnrollment`, `session.add`; uses database session queries, database writes, idempotency lookup, outbox/event emission, policy validation, serialization/projection, time calculations.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`.

##### `async get_sequence_enrollment(enrollment_id: str, *, settings: Settings | None = None) -> SequenceEnrollmentOut | None`

- Inputs: `enrollment_id` (str), `settings` (Settings | None)
- Output: Returns `SequenceEnrollmentOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `get_sequence_enrollment` loads one record or detail object for API or workflow callers.
- How: It calls `session_scope`, `session.get`, `_enrollment_to_model_with_emails`; uses database session queries, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async list_sequence_enrollments(*, status: str | None = None, limit: int = 100, settings: Settings | None = None) -> SequenceEnrollmentList`

- Inputs: `status` (str | None), `limit` (int), `settings` (Settings | None)
- Output: Returns `SequenceEnrollmentList`.
- Why: `list_sequence_enrollments` retrieves a bounded collection for API or workflow callers.
- How: It calls `session_scope`, `limit`, `SequenceEnrollmentList`, `query.where`, `session.execute`, `order_by`, `_enrollment_to_model_with_emails`, `result.scalars`; uses database session queries, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async pause_sequence_enrollment(enrollment_id: str, request: SequenceEnrollmentActionRequest, *, actor: str, settings: Settings | None = None) -> SequenceEnrollmentOut | None`

- Inputs: `enrollment_id` (str), `request` (SequenceEnrollmentActionRequest), `actor` (str), `settings` (Settings | None)
- Output: Returns `SequenceEnrollmentOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `pause_sequence_enrollment` provides the src/ghostrecon/services/sequencing/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_set_enrollment_status`; uses outbox/event emission.
- Side effects: adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async resume_sequence_enrollment(enrollment_id: str, request: SequenceEnrollmentActionRequest, *, actor: str, settings: Settings | None = None) -> SequenceEnrollmentOut | None`

- Inputs: `enrollment_id` (str), `request` (SequenceEnrollmentActionRequest), `actor` (str), `settings` (Settings | None)
- Output: Returns `SequenceEnrollmentOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `resume_sequence_enrollment` provides the src/ghostrecon/services/sequencing/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `session_scope`, `utcnow`, `session.get`, `ValueError`, `_enrollment_to_model_with_emails`; uses database session queries, serialization/projection, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`; may return `None` for not-found or unavailable data.

##### `async cancel_sequence_enrollment(enrollment_id: str, request: SequenceEnrollmentActionRequest, *, actor: str, settings: Settings | None = None) -> SequenceEnrollmentOut | None`

- Inputs: `enrollment_id` (str), `request` (SequenceEnrollmentActionRequest), `actor` (str), `settings` (Settings | None)
- Output: Returns `SequenceEnrollmentOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `cancel_sequence_enrollment` provides the src/ghostrecon/services/sequencing/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_set_enrollment_status`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async process_due_sequence_steps(*, limit: int = 50, settings: Settings | None = None, sender: SmtpSender | None = None) -> dict[str, object]`

- Inputs: `limit` (int), `settings` (Settings | None), `sender` (SmtpSender | None)
- Output: Returns `dict[str, object]`.
- Why: `process_due_sequence_steps` executes queued workflow work and records resulting state transitions.
- How: It calls `utcnow`, `get_settings`, `session_scope`, `outcomes.append`, `session.execute`, `limit`, `result.scalars`, `send_next_sequence_step`; uses database session queries, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async send_next_sequence_step(enrollment_id: str, *, settings: Settings | None = None, sender: SmtpSender | None = None) -> dict[str, object]`

- Inputs: `enrollment_id` (str), `settings` (Settings | None), `sender` (SmtpSender | None)
- Output: Returns `dict[str, object]`.
- Why: `send_next_sequence_step` provides the src/ghostrecon/services/sequencing/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_settings`, `StdlibSmtpSender`, `session_scope`, `_domain_from_email`, `lower`, `utcnow`, `_enqueue_event`, `session.get`; uses database session queries, outbox/event emission, parsing/normalization, policy validation, serialization/projection, time calculations.
- Side effects: adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`; catches provider or validation errors and maps them to the module contract.

##### `async process_inbound_email_event(request: InboundEmailEventCreate, *, idempotency_key: str, settings: Settings | None = None) -> InboundEmailEventOut`

- Inputs: `request` (InboundEmailEventCreate), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `InboundEmailEventOut`.
- Why: `process_inbound_email_event` executes queued workflow work and records resulting state transitions.
- How: It calls `session_scope`, `InboundEmailEvent`, `session.add`, `inbound_event_to_model`, `session.scalar`, `_find_outbound_for_inbound`, `utcnow`, `session.flush`; uses database session queries, database writes, idempotency lookup, outbox/event emission, parsing/normalization, policy validation, serialization/projection, time calculations.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async process_unsubscribe(request: UnsubscribeRequest, *, idempotency_key: str, settings: Settings | None = None) -> InboundEmailEventOut`

- Inputs: `request` (UnsubscribeRequest), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `InboundEmailEventOut`.
- Why: `process_unsubscribe` executes queued workflow work and records resulting state transitions.
- How: It calls `process_inbound_email_event`, `InboundEmailEventCreate`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async poll_inbound_email_events(*, limit: int = 50, settings: Settings | None = None, poller: ImapPoller | None = None) -> dict[str, object]`

- Inputs: `limit` (int), `settings` (Settings | None), `poller` (ImapPoller | None)
- Output: Returns `dict[str, object]`.
- Why: `poll_inbound_email_events` provides the src/ghostrecon/services/sequencing/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `imap_poller.poll`, `get_settings`, `StdlibImapPoller`, `processed.append`, `uuid4`, `process_inbound_email_event`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `sequence_step_to_model(step: SequenceStep) -> SequenceStepOut`

- Inputs: `step` (SequenceStep)
- Output: Returns `SequenceStepOut`.
- Why: `sequence_step_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `SequenceStepOut`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `sequence_to_model(sequence: Sequence, steps: list[SequenceStep]) -> SequenceOut`

- Inputs: `sequence` (Sequence), `steps` (list[SequenceStep])
- Output: Returns `SequenceOut`.
- Why: `sequence_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `SequenceOut`, `sequence_step_to_model`; uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `outbound_email_to_api(outbound: OutboundEmail) -> dict[str, object]`

- Inputs: `outbound` (OutboundEmail)
- Output: Returns `dict[str, object]`.
- Why: `outbound_email_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `outbound_email_to_model(outbound: OutboundEmail) -> OutboundEmailOut`

- Inputs: `outbound` (OutboundEmail)
- Output: Returns `OutboundEmailOut`.
- Why: `outbound_email_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `OutboundEmailOut.model_validate`, `outbound_email_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `sequence_enrollment_to_api(enrollment: SequenceEnrollment) -> dict[str, object]`

- Inputs: `enrollment` (SequenceEnrollment)
- Output: Returns `dict[str, object]`.
- Why: `sequence_enrollment_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `sequence_enrollment_to_model(enrollment: SequenceEnrollment, outbound_emails: list[OutboundEmail] | None = None) -> SequenceEnrollmentOut`

- Inputs: `enrollment` (SequenceEnrollment), `outbound_emails` (list[OutboundEmail] | None)
- Output: Returns `SequenceEnrollmentOut`.
- Why: `sequence_enrollment_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `sequence_enrollment_to_api`, `SequenceEnrollmentOut.model_validate`, `outbound_email_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `inbound_event_to_api(event: InboundEmailEvent) -> dict[str, object]`

- Inputs: `event` (InboundEmailEvent)
- Output: Returns `dict[str, object]`.
- Why: `inbound_event_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `inbound_event_to_model(event: InboundEmailEvent) -> InboundEmailEventOut`

- Inputs: `event` (InboundEmailEvent)
- Output: Returns `InboundEmailEventOut`.
- Why: `inbound_event_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `InboundEmailEventOut.model_validate`, `inbound_event_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _sequence_steps(session: Any, sequence_id: str) -> list[SequenceStep]`

- Inputs: `session` (Any), `sequence_id` (str)
- Output: Returns `list[SequenceStep]`.
- Why: `_sequence_steps` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session.execute`, `result.scalars`, `order_by`, `where`, `is_`, `select`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _enrollment_to_model_with_emails(session: Any, enrollment: SequenceEnrollment) -> SequenceEnrollmentOut`

- Inputs: `session` (Any), `enrollment` (SequenceEnrollment)
- Output: Returns `SequenceEnrollmentOut`.
- Why: `_enrollment_to_model_with_emails` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `sequence_enrollment_to_model`, `session.execute`, `order_by`, `result.scalars`, `where`, `select`; uses database session queries, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _set_enrollment_status(enrollment_id: str, *, status: str, reason: str, event_name: EventName | None, settings: Settings | None) -> SequenceEnrollmentOut | None`

- Inputs: `enrollment_id` (str), `status` (str), `reason` (str), `event_name` (EventName | None), `settings` (Settings | None)
- Output: Returns `SequenceEnrollmentOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `_set_enrollment_status` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session_scope`, `utcnow`, `session.get`, `ValueError`, `_enqueue_event`, `_enrollment_to_model_with_emails`, `sequence_enrollment_to_api`; uses database session queries, outbox/event emission, serialization/projection, time calculations.
- Side effects: adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`; may return `None` for not-found or unavailable data.

##### `async _contact_for_target(session: Any, target: CrmTarget, requested_contact_id: str | None) -> Contact`

- Inputs: `session` (Any), `target` (CrmTarget), `requested_contact_id` (str | None)
- Output: Returns `Contact`.
- Why: `_contact_for_target` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `ValueError`, `session.get`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`.

##### `_require_sendable_contact(contact: Contact) -> None`

- Inputs: `contact` (Contact)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_require_sendable_contact` centralizes a validation gate and raises when the invariant is not satisfied.
- How: It calls `ValueError`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `ValueError`; may return `None` for not-found or unavailable data.

##### `async _suppression_allowed(session: Any, *, email: str | None, domain: str | None, contact_id: str | None, channel: str) -> Any`

- Inputs: `session` (Any), `email` (str | None), `domain` (str | None), `contact_id` (str | None), `channel` (str)
- Output: Returns `Any`.
- Why: `_suppression_allowed` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `evaluate_suppression`, `baseline.model_copy`, `SuppressionCheckRequest`, `matches.append`, `session.scalar`, `limit`, `email.lower`, `domain.lower`; uses database session queries, parsing/normalization, policy validation, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _step_for_order(session: Any, sequence_id: str, step_order: int) -> SequenceStep | None`

- Inputs: `session` (Any), `sequence_id` (str), `step_order` (int)
- Output: Returns `SequenceStep | None`; callers must handle the documented not-found or unavailable path.
- Why: `_step_for_order` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session.scalar`, `where`, `is_`, `select`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async _outbound_for_step(session: Any, enrollment: SequenceEnrollment, step: SequenceStep, contact: Contact, account: Account | None, from_email: str) -> OutboundEmail`

- Inputs: `session` (Any), `enrollment` (SequenceEnrollment), `step` (SequenceStep), `contact` (Contact), `account` (Account | None), `from_email` (str)
- Output: Returns `OutboundEmail`.
- Why: `_outbound_for_step` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `utcnow`, `OutboundEmail`, `session.add`, `session.scalar`, `session.flush`, `where`, `lower`, `_render_template`; uses database session queries, database writes, idempotency lookup, parsing/normalization, time calculations.
- Side effects: mutates database state; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _advance_enrollment(session: Any, enrollment: SequenceEnrollment, current_step: SequenceStep) -> None`

- Inputs: `session` (Any), `enrollment` (SequenceEnrollment), `current_step` (SequenceStep)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_advance_enrollment` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `utcnow`, `_sequence_steps`, `_complete_enrollment`, `timedelta`; uses time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `_complete_enrollment(session: Any, enrollment: SequenceEnrollment) -> None`

- Inputs: `session` (Any), `enrollment` (SequenceEnrollment)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_complete_enrollment` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `utcnow`, `_enqueue_event`, `sequence_enrollment_to_api`; uses outbox/event emission, serialization/projection, time calculations.
- Side effects: adds outbox/event records.
- Failures: may return `None` for not-found or unavailable data.

##### `async _pause_for_policy(session: Any, enrollment: SequenceEnrollment, reason: str) -> None`

- Inputs: `session` (Any), `enrollment` (SequenceEnrollment), `reason` (str)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_pause_for_policy` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `utcnow`, `_enqueue_event`, `sequence_enrollment_to_api`; uses outbox/event emission, policy validation, serialization/projection, time calculations.
- Side effects: adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async _suppress_enrollment(session: Any, enrollment: SequenceEnrollment, contact: Contact, reason: str | None) -> None`

- Inputs: `session` (Any), `enrollment` (SequenceEnrollment), `contact` (Contact), `reason` (str | None)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_suppress_enrollment` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `utcnow`, `session.add`, `_enqueue_event`, `SequenceSuppressionEvent`, `sequence_enrollment_to_api`, `_domain_from_email`, `lower`; uses database writes, outbox/event emission, parsing/normalization, policy validation, serialization/projection, time calculations.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async _rate_limit_blocker(session: Any, *, to_email: str, from_email: str, channel: str, sequence: Sequence, settings: Settings) -> str | None`

- Inputs: `session` (Any), `to_email` (str), `from_email` (str), `channel` (str), `sequence` (Sequence), `settings` (Settings)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_rate_limit_blocker` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_domain_from_email`, `utcnow`, `timedelta`, `session.execute`, `result.scalars`, `policy.get`, `where`, `lower`; uses database session queries, parsing/normalization, policy validation, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async _find_outbound_for_inbound(session: Any, request: InboundEmailEventCreate) -> OutboundEmail | None`

- Inputs: `session` (Any), `request` (InboundEmailEventCreate)
- Output: Returns `OutboundEmail | None`; callers must handle the documented not-found or unavailable path.
- Why: `_find_outbound_for_inbound` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `lower`, `session.scalar`, `limit`, `order_by`, `desc`, `where`, `select`; uses database session queries, parsing/normalization.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async _find_enrollment_by_email(session: Any, email: str | None) -> SequenceEnrollment | None`

- Inputs: `session` (Any), `email` (str | None)
- Output: Returns `SequenceEnrollment | None`; callers must handle the documented not-found or unavailable path.
- Why: `_find_enrollment_by_email` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session.scalar`, `limit`, `session.get`, `order_by`, `desc`, `where`, `select`, `lower`; uses database session queries, parsing/normalization.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async _create_unsubscribe_suppression(session: Any, *, email: str, channel: str, reason: str, source_event: InboundEmailEvent, enrollment: SequenceEnrollment | None) -> None`

- Inputs: `session` (Any), `email` (str), `channel` (str), `reason` (str), `source_event` (InboundEmailEvent), `enrollment` (SequenceEnrollment | None)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_create_unsubscribe_suppression` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_domain_from_email`, `session.add`, `session.scalar`, `Suppression`, `_enqueue_event`, `SequenceSuppressionEvent`, `limit`, `session.flush`; uses database session queries, database writes, idempotency lookup, outbox/event emission, parsing/normalization, policy validation.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `_enqueue_event(session: Any, event_name: EventName, aggregate_type: str, aggregate_id: str, payload: dict[str, object], idempotency_key: str) -> OutboxEvent`

- Inputs: `session` (Any), `event_name` (EventName), `aggregate_type` (str), `aggregate_id` (str), `payload` (dict[str, object]), `idempotency_key` (str)
- Output: Returns `OutboxEvent`.
- Why: `_enqueue_event` creates an outbox event record for asynchronous consumers.
- How: It calls `new_event`, `OutboxEvent`, `session.add`, `event.model_dump`; uses database writes, idempotency lookup, outbox/event emission, serialization/projection.
- Side effects: mutates database state; adds outbox/event records.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_domain_from_email(email: str | None) -> str | None`

- Inputs: `email` (str | None)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_domain_from_email` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `lower`, `email.rsplit`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_render_template(template: str, contact: Contact, account: Account | None) -> str`

- Inputs: `template` (str), `contact` (Contact), `account` (Account | None)
- Output: Returns `str`.
- Why: `_render_template` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `template.format_map`, `_SafeFormat`, `parse`, `split`, `Formatter`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `utcnow() -> datetime`

- Inputs: No external inputs.
- Output: Returns `datetime`.
- Why: `utcnow` provides the src/ghostrecon/services/sequencing/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `datetime.now`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

### `src/ghostrecon/services/sequence_adapters.py`

#### Classes

##### `SmtpSendRequest`

`SmtpSendRequest` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `from_email` (str), `to_email` (str), `subject` (str), `body` (str), `message_id` (str).

##### `SmtpSendResult`

`SmtpSendResult` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `provider_message_id` (str).

##### `SmtpSender`

`SmtpSender` is a protocol/interface based on `Protocol`. Fields: none declared at class level.

- `send(request: SmtpSendRequest) -> SmtpSendResult`
  - Inputs: `request` (SmtpSendRequest)
  - Output: Returns `SmtpSendResult`.
  - Why: `SmtpSender.send` provides the src/ghostrecon/services/sequence_adapters.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `ImapPoller`

`ImapPoller` is a protocol/interface based on `Protocol`. Fields: none declared at class level.

- `poll(limit: int = 50) -> list[InboundEmailEventCreate]`
  - Inputs: `limit` (int)
  - Output: Returns `list[InboundEmailEventCreate]`.
  - Why: `ImapPoller.poll` provides the src/ghostrecon/services/sequence_adapters.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `StdlibSmtpSender`

`StdlibSmtpSender` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `__init__(settings: Settings) -> None`
  - Inputs: `settings` (Settings)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes StdlibSmtpSender with the provider, settings, or client state needed by later calls.
  - How: It calls `ValueError`.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: raises `ValueError`; may return `None` for not-found or unavailable data.
- `send(request: SmtpSendRequest) -> SmtpSendResult`
  - Inputs: `request` (SmtpSendRequest)
  - Output: Returns `SmtpSendResult`.
  - Why: `StdlibSmtpSender.send` provides the src/ghostrecon/services/sequence_adapters.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `EmailMessage`, `message.set_content`, `SmtpSendResult`, `smtplib.SMTP`, `smtp.send_message`, `smtp.starttls`, `smtp.login`; uses HTTP/provider IO.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `StdlibImapPoller`

`StdlibImapPoller` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `__init__(settings: Settings) -> None`
  - Inputs: `settings` (Settings)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes StdlibImapPoller with the provider, settings, or client state needed by later calls.
  - How: It calls `ValueError`.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: raises `ValueError`; may return `None` for not-found or unavailable data.
- `poll(limit: int = 50) -> list[InboundEmailEventCreate]`
  - Inputs: `limit` (int)
  - Output: Returns `list[InboundEmailEventCreate]`.
  - Why: `StdlibImapPoller.poll` provides the src/ghostrecon/services/sequence_adapters.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `imaplib.IMAP4_SSL`, `imap.login`, `imap.select`, `imap.search`, `split`, `imap.fetch`, `next`, `message_from_bytes`; uses HTTP/provider IO, database session queries, parsing/normalization.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

#### Module Functions

##### `_classify_inbound(subject: str, from_email: str | None) -> InboundEmailEventType`

- Inputs: `subject` (str), `from_email` (str | None)
- Output: Returns `InboundEmailEventType`.
- Why: `_classify_inbound` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `subject.lower`, `lower`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_extract_address(raw: str | None) -> str | None`

- Inputs: `raw` (str | None)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_extract_address` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `lower`, `raw.strip`, `split`, `raw.split`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_sequence_eligibility.py`
- `tests/unit/test_sequence_runtime.py`

## Startup and dependency contract

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns database, Attio, SMTP, IMAP, and Google Calendar. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Database-owning APIs verify the migrated schema; configured provider checks are named without exposing credentials.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
