
# meeting-handoff-service Technical README

## Architecture

Meeting Handoff Service is implemented by `src/ghostrecon/services/meeting/`, `src/ghostrecon/services/calendar_adapters/`. It is exposed through `meeting_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | `POST` | `/v1/calendar/availability` | `calendar_availability` |
| service | `POST` | `/v1/meetings` | `meeting_create` |
| service | `GET` | `/v1/meetings` | `meeting_list` |
| service | `GET` | `/v1/meetings/{meeting_id}` | `meeting_detail` |
| service | `POST` | `/v1/meetings/{meeting_id}/prep-packet` | `meeting_generate_prep_packet` |
| service | `POST` | `/v1/meetings/{meeting_id}/outcome` | `meeting_record_outcome` |
| service | `POST` | `/v1/meetings/{meeting_id}/cancel` | `meeting_cancel` |
| service | `POST` | `/v1/meetings/{meeting_id}/retry-sync` | `meeting_retry_sync` |
| service | `POST` | `/v1/meetings/prep-packet` | `prep_packet` |
| gateway | `POST` | `/v1/calendar/availability` | `calendar_availability` |
| gateway | `POST` | `/v1/meetings` | `meeting_create` |
| gateway | `GET` | `/v1/meetings` | `meeting_list` |
| gateway | `GET` | `/v1/meetings/{meeting_id}` | `meeting_detail` |
| gateway | `POST` | `/v1/meetings/{meeting_id}/prep-packet` | `meeting_generate_prep_packet` |
| gateway | `POST` | `/v1/meetings/{meeting_id}/outcome` | `meeting_record_outcome` |
| gateway | `POST` | `/v1/meetings/{meeting_id}/cancel` | `meeting_cancel` |
| gateway | `POST` | `/v1/meetings/{meeting_id}/retry-sync` | `meeting_retry_sync` |
| gateway | `POST` | `/v1/meetings/prep-packet` | `prep_packet` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.

## Function Reference

### `src/ghostrecon/services/meeting/`

#### Module Functions

##### `build_prep_packet(request: PrepPacketRequest) -> PrepPacket`

- Inputs: `request` (PrepPacketRequest)
- Output: Returns `PrepPacket`.
- Why: `build_prep_packet` derives a stable request, key, or projection object from richer inputs.
- How: It calls `PrepPacket`, `get`, `contact.get`, `signal.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async create_meeting(request: MeetingCreateRequest, *, actor: str, idempotency_key: str, settings: Settings | None = None, calendar_client: CalendarClient | None = None) -> MeetingHandoffOut`

- Inputs: `request` (MeetingCreateRequest), `actor` (str), `idempotency_key` (str), `settings` (Settings | None), `calendar_client` (CalendarClient | None)
- Output: Returns `MeetingHandoffOut`.
- Why: `create_meeting` creates and persists a new domain object while enforcing idempotency and policy.
- How: It calls `_require_time_window`, `get_settings`, `calendar_client_for_settings`, `session_scope`, `_require_exported_target`, `_meeting_attendees`, `utcnow`, `MeetingHandoff`; uses database session queries, database writes, idempotency lookup, outbox/event emission, policy validation, serialization/projection, time calculations.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`.

##### `async list_meetings(*, status: str | None = None, crm_target_id: str | None = None, limit: int = 100, settings: Settings | None = None) -> MeetingHandoffList`

- Inputs: `status` (str | None), `crm_target_id` (str | None), `limit` (int), `settings` (Settings | None)
- Output: Returns `MeetingHandoffList`.
- Why: `list_meetings` retrieves a bounded collection for API or workflow callers.
- How: It calls `MeetingHandoffList`, `session_scope`, `order_by`, `desc`, `asc`, `stmt.where`, `scalars`, `select`; uses database session queries, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_meeting(meeting_id: str, *, settings: Settings | None = None) -> MeetingHandoffOut | None`

- Inputs: `meeting_id` (str), `settings` (Settings | None)
- Output: Returns `MeetingHandoffOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `get_meeting` loads one record or detail object for API or workflow callers.
- How: It calls `session_scope`, `session.get`, `_meeting_to_model_with_children`; uses database session queries, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async generate_meeting_prep_packet(meeting_id: str, *, actor: str, idempotency_key: str | None = None, settings: Settings | None = None) -> MeetingHandoffOut | None`

- Inputs: `meeting_id` (str), `actor` (str), `idempotency_key` (str | None), `settings` (Settings | None)
- Output: Returns `MeetingHandoffOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `generate_meeting_prep_packet` provides the src/ghostrecon/services/meeting/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `session_scope`, `build_prep_packet`, `utcnow`, `MeetingPrepPacket`, `session.add`, `_enqueue_event`, `session.get`, `_latest_prep_packet`; uses database session queries, database writes, idempotency lookup, outbox/event emission, serialization/projection, time calculations.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async record_meeting_outcome(meeting_id: str, request: MeetingOutcomeRequest, *, actor: str, idempotency_key: str, settings: Settings | None = None, crm_client: CrmClient | None = None) -> MeetingHandoffOut | None`

- Inputs: `meeting_id` (str), `request` (MeetingOutcomeRequest), `actor` (str), `idempotency_key` (str), `settings` (Settings | None), `crm_client` (CrmClient | None)
- Output: Returns `MeetingHandoffOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `record_meeting_outcome` provides the src/ghostrecon/services/meeting/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_settings`, `session_scope`, `utcnow`, `_enqueue_event`, `session.get`, `session.scalar`, `_create_follow_up_tasks`, `meeting_to_api`; uses database session queries, idempotency lookup, outbox/event emission, serialization/projection, time calculations.
- Side effects: adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async retry_meeting_crm_sync(meeting_id: str, *, actor: str, settings: Settings | None = None, crm_client: CrmClient | None = None) -> MeetingHandoffOut | None`

- Inputs: `meeting_id` (str), `actor` (str), `settings` (Settings | None), `crm_client` (CrmClient | None)
- Output: Returns `MeetingHandoffOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `retry_meeting_crm_sync` requeues or reattempts previously failed work in a controlled way.
- How: It calls `get_settings`, `session_scope`, `session.get`, `_sync_meeting_to_crm`, `_meeting_to_model_with_children`; uses database session queries, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async cancel_meeting(meeting_id: str, request: MeetingActionRequest, *, actor: str, settings: Settings | None = None, calendar_client: CalendarClient | None = None) -> MeetingHandoffOut | None`

- Inputs: `meeting_id` (str), `request` (MeetingActionRequest), `actor` (str), `settings` (Settings | None), `calendar_client` (CalendarClient | None)
- Output: Returns `MeetingHandoffOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `cancel_meeting` provides the src/ghostrecon/services/meeting/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_settings`, `calendar_client_for_settings`, `session_scope`, `utcnow`, `session.get`, `_meeting_to_model_with_children`, `client.cancel_event`; uses database session queries, serialization/projection, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async get_calendar_availability(request: CalendarAvailabilityRequest, *, settings: Settings | None = None, calendar_client: CalendarClient | None = None) -> CalendarAvailabilityResult`

- Inputs: `request` (CalendarAvailabilityRequest), `settings` (Settings | None), `calendar_client` (CalendarClient | None)
- Output: Returns `CalendarAvailabilityResult`.
- Why: `get_calendar_availability` loads one record or detail object for API or workflow callers.
- How: It calls `CalendarAvailabilityResult`, `ValueError`, `get_settings`, `calendar_client_for_settings`, `client.get_availability`, `lower`; uses parsing/normalization.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`.

##### `meeting_to_api(meeting: MeetingHandoff) -> dict[str, object]`

- Inputs: `meeting` (MeetingHandoff)
- Output: Returns `dict[str, object]`.
- Why: `meeting_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `meeting_to_model(meeting: MeetingHandoff, *, prep_packet: MeetingPrepPacket | None = None, follow_up_tasks: list[MeetingFollowUpTask] | None = None) -> MeetingHandoffOut`

- Inputs: `meeting` (MeetingHandoff), `prep_packet` (MeetingPrepPacket | None), `follow_up_tasks` (list[MeetingFollowUpTask] | None)
- Output: Returns `MeetingHandoffOut`.
- Why: `meeting_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `meeting_to_api`, `MeetingHandoffOut.model_validate`, `meeting_prep_packet_to_api`, `meeting_follow_up_task_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `meeting_prep_packet_to_api(packet: MeetingPrepPacket) -> dict[str, object]`

- Inputs: `packet` (MeetingPrepPacket)
- Output: Returns `dict[str, object]`.
- Why: `meeting_prep_packet_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `meeting_prep_packet_to_model(packet: MeetingPrepPacket) -> MeetingPrepPacketOut`

- Inputs: `packet` (MeetingPrepPacket)
- Output: Returns `MeetingPrepPacketOut`.
- Why: `meeting_prep_packet_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `MeetingPrepPacketOut.model_validate`, `meeting_prep_packet_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `meeting_follow_up_task_to_api(task: MeetingFollowUpTask) -> dict[str, object]`

- Inputs: `task` (MeetingFollowUpTask)
- Output: Returns `dict[str, object]`.
- Why: `meeting_follow_up_task_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `meeting_follow_up_task_to_model(task: MeetingFollowUpTask) -> MeetingFollowUpTaskOut`

- Inputs: `task` (MeetingFollowUpTask)
- Output: Returns `MeetingFollowUpTaskOut`.
- Why: `meeting_follow_up_task_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `MeetingFollowUpTaskOut.model_validate`, `meeting_follow_up_task_to_api`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _meeting_to_model_with_children(session: Any, meeting: MeetingHandoff) -> MeetingHandoffOut`

- Inputs: `session` (Any), `meeting` (MeetingHandoff)
- Output: Returns `MeetingHandoffOut`.
- Why: `_meeting_to_model_with_children` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `meeting_to_model`, `_latest_prep_packet`, `session.execute`, `order_by`, `asc`, `result.scalars`, `where`, `select`; uses database session queries, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _latest_prep_packet(session: Any, meeting_id: str) -> MeetingPrepPacket | None`

- Inputs: `session` (Any), `meeting_id` (str)
- Output: Returns `MeetingPrepPacket | None`; callers must handle the documented not-found or unavailable path.
- Why: `_latest_prep_packet` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session.scalar`, `limit`, `order_by`, `desc`, `where`, `select`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async _prep_request_for_meeting(session: Any, meeting: MeetingHandoff) -> tuple[PrepPacketRequest, dict[str, object]]`

- Inputs: `session` (Any), `meeting` (MeetingHandoff)
- Output: Returns `tuple[PrepPacketRequest, dict[str, object]]`.
- Why: `_prep_request_for_meeting` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `signal_payloads.extend`, `PrepPacketRequest`, `session.get`, `session.execute`, `result.scalars`, `_target_signals`, `order_by`, `limit`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _target_signals(session: Any, target: CrmTarget | None) -> list[dict[str, object]]`

- Inputs: `session` (Any), `target` (CrmTarget | None)
- Output: Returns `list[dict[str, object]]`.
- Why: `_target_signals` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session.get`, `join`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _create_follow_up_tasks(session: Any, meeting: MeetingHandoff, requests: list[MeetingFollowUpTaskCreate]) -> list[MeetingFollowUpTask]`

- Inputs: `session` (Any), `meeting` (MeetingHandoff), `requests` (list[MeetingFollowUpTaskCreate])
- Output: Returns `list[MeetingFollowUpTask]`.
- Why: `_create_follow_up_tasks` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `utcnow`, `enumerate`, `MeetingFollowUpTask`, `session.add`, `tasks.append`, `session.flush`, `session.scalar`, `lower`; uses database session queries, database writes, idempotency lookup, parsing/normalization, time calculations.
- Side effects: mutates database state; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _sync_meeting_to_crm(session: Any, meeting: MeetingHandoff, *, actor: str, settings: Settings, client: CrmClient | None) -> None`

- Inputs: `session` (Any), `meeting` (MeetingHandoff), `actor` (str), `settings` (Settings), `client` (CrmClient | None)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_sync_meeting_to_crm` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_crm_sync_plan`, `utcnow`, `_enqueue_event`, `scalars`, `AttioCrmClient`, `crm.sync`, `isinstance`, `session.execute`; uses database session queries, outbox/event emission, time calculations.
- Side effects: adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data; catches provider or validation errors and maps them to the module contract.

##### `_crm_sync_plan(meeting: MeetingHandoff, tasks: list[MeetingFollowUpTask], *, actor: str, settings: Settings) -> CrmSyncPlan`

- Inputs: `meeting` (MeetingHandoff), `tasks` (list[MeetingFollowUpTask]), `actor` (str), `settings` (Settings)
- Output: Returns `CrmSyncPlan`.
- Why: `_crm_sync_plan` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `CrmSyncPlan`, `_iso`, `meeting_follow_up_task_to_api`; uses parsing/normalization, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _contact_for_meeting(session: Any, target: CrmTarget | None, requested_contact_id: str | None) -> Contact | None`

- Inputs: `session` (Any), `target` (CrmTarget | None), `requested_contact_id` (str | None)
- Output: Returns `Contact | None`; callers must handle the documented not-found or unavailable path.
- Why: `_contact_for_meeting` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session.get`, `ValueError`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`; may return `None` for not-found or unavailable data.

##### `_meeting_attendees(requested: list[MeetingAttendee], contact: Contact | None) -> list[MeetingAttendee]`

- Inputs: `requested` (list[MeetingAttendee]), `contact` (Contact | None)
- Output: Returns `list[MeetingAttendee]`.
- Why: `_meeting_attendees` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `lower`, `attendees.append`, `ValueError`, `MeetingAttendee`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `ValueError`.

##### `async _ensure_invite_allowed(session: Any, attendees: list[MeetingAttendee], contact: Contact | None) -> None`

- Inputs: `session` (Any), `attendees` (list[MeetingAttendee]), `contact` (Contact | None)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_ensure_invite_allowed` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `lower`, `_domain_from_email`, `evaluate_suppression`, `SuppressionCheckRequest`, `ValueError`, `clauses.append`, `session.scalar`, `limit`; uses database session queries, parsing/normalization, policy validation, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`; may return `None` for not-found or unavailable data.

##### `_complete_sequence_for_meeting(session: Any, enrollment: SequenceEnrollment) -> None`

- Inputs: `session` (Any), `enrollment` (SequenceEnrollment)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_complete_sequence_for_meeting` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `utcnow`, `_enqueue_event`; uses outbox/event emission, policy validation, time calculations.
- Side effects: adds outbox/event records.
- Failures: may return `None` for not-found or unavailable data.

##### `_require_exported_target(target: CrmTarget | None) -> None`

- Inputs: `target` (CrmTarget | None)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_require_exported_target` centralizes a validation gate and raises when the invariant is not satisfied.
- How: It calls `ValueError`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `ValueError`; may return `None` for not-found or unavailable data.

##### `_require_time_window(start_at: datetime, end_at: datetime) -> None`

- Inputs: `start_at` (datetime), `end_at` (datetime)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_require_time_window` centralizes a validation gate and raises when the invariant is not satisfied.
- How: It calls `ValueError`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `ValueError`; may return `None` for not-found or unavailable data.

##### `_enqueue_event(session: Any, event_name: EventName, aggregate_type: str, aggregate_id: str, payload: dict[str, object], idempotency_key: str, *, source_service: str = MEETING_SERVICE_NAME) -> OutboxEvent`

- Inputs: `session` (Any), `event_name` (EventName), `aggregate_type` (str), `aggregate_id` (str), `payload` (dict[str, object]), `idempotency_key` (str), `source_service` (str)
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

##### `_iso(value: datetime | None) -> str | None`

- Inputs: `value` (datetime | None)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_iso` formats datetime values for API-safe JSON output.
- How: It calls `value.isoformat`, `value.replace`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `utcnow() -> datetime`

- Inputs: No external inputs.
- Output: Returns `datetime`.
- Why: `utcnow` provides the src/ghostrecon/services/meeting/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `datetime.now`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

### `src/ghostrecon/services/calendar_adapters/`

#### Classes

##### `CalendarProviderError`

`CalendarProviderError` is a data container or runtime class based on `RuntimeError`. Fields: none declared at class level.

- `__init__(message: str, *, retryable: bool = False, retry_after_seconds: int | None = None) -> None`
  - Inputs: `message` (str), `retryable` (bool), `retry_after_seconds` (int | None)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes CalendarProviderError with the provider, settings, or client state needed by later calls.
  - How: It calls `__init__`, `super`.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.

##### `CalendarEventRequest`

`CalendarEventRequest` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `meeting_id` (str), `subject` (str), `start_at` (datetime), `end_at` (datetime), `timezone` (str), `attendees` (list[MeetingAttendee]), `description` (str | None), `location` (str | None), `send_updates` (bool).

##### `CalendarEventResult`

`CalendarEventResult` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `provider_event_id` (str), `calendar_id` (str), `html_link` (str | None), `raw_response` (dict[str, Any]).

##### `CalendarClient`

`CalendarClient` is a protocol/interface based on `Protocol`. Fields: `provider` (str).

- `async create_event(request: CalendarEventRequest) -> CalendarEventResult`
  - Inputs: `request` (CalendarEventRequest)
  - Output: Returns `CalendarEventResult`.
  - Why: `CalendarClient.create_event` creates and persists a new domain object while enforcing idempotency and policy.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async update_event(provider_event_id: str, request: CalendarEventRequest) -> CalendarEventResult`
  - Inputs: `provider_event_id` (str), `request` (CalendarEventRequest)
  - Output: Returns `CalendarEventResult`.
  - Why: `CalendarClient.update_event` provides the src/ghostrecon/services/calendar_adapters/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async cancel_event(provider_event_id: str, *, send_updates: bool = True) -> None`
  - Inputs: `provider_event_id` (str), `send_updates` (bool)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: `CalendarClient.cancel_event` provides the src/ghostrecon/services/calendar_adapters/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: may return `None` for not-found or unavailable data.
- `async get_availability(*, attendees: list[str], time_min: datetime, time_max: datetime, timezone: str) -> dict[str, list[CalendarBusySlot]]`
  - Inputs: `attendees` (list[str]), `time_min` (datetime), `time_max` (datetime), `timezone` (str)
  - Output: Returns `dict[str, list[CalendarBusySlot]]`.
  - Why: `CalendarClient.get_availability` loads one record or detail object for API or workflow callers.
  - How: It uses time calculations.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `FakeCalendarClient`

`FakeCalendarClient` is a data container or runtime class based on `object`. Fields: `provider`.

- `__init__(calendar_id: str = 'fake-calendar') -> None`
  - Inputs: `calendar_id` (str)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes FakeCalendarClient with the provider, settings, or client state needed by later calls.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.
- `async create_event(request: CalendarEventRequest) -> CalendarEventResult`
  - Inputs: `request` (CalendarEventRequest)
  - Output: Returns `CalendarEventResult`.
  - Why: `FakeCalendarClient.create_event` creates and persists a new domain object while enforcing idempotency and policy.
  - How: It calls `_google_event_body`, `CalendarEventResult`.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async update_event(provider_event_id: str, request: CalendarEventRequest) -> CalendarEventResult`
  - Inputs: `provider_event_id` (str), `request` (CalendarEventRequest)
  - Output: Returns `CalendarEventResult`.
  - Why: `FakeCalendarClient.update_event` provides the src/ghostrecon/services/calendar_adapters/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `_google_event_body`, `CalendarEventResult`.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async cancel_event(provider_event_id: str, *, send_updates: bool = True) -> None`
  - Inputs: `provider_event_id` (str), `send_updates` (bool)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: `FakeCalendarClient.cancel_event` provides the src/ghostrecon/services/calendar_adapters/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `pop`.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: may return `None` for not-found or unavailable data.
- `async get_availability(*, attendees: list[str], time_min: datetime, time_max: datetime, timezone: str) -> dict[str, list[CalendarBusySlot]]`
  - Inputs: `attendees` (list[str]), `time_min` (datetime), `time_max` (datetime), `timezone` (str)
  - Output: Returns `dict[str, list[CalendarBusySlot]]`.
  - Why: `FakeCalendarClient.get_availability` loads one record or detail object for API or workflow callers.
  - How: It calls `attendee.lower`; uses parsing/normalization, time calculations.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `GoogleCalendarClient`

`GoogleCalendarClient` is a data container or runtime class based on `object`. Fields: `provider`, `token_url`, `calendar_api_base`, `scopes`.

- `__init__(settings: Settings) -> None`
  - Inputs: `settings` (Settings)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes GoogleCalendarClient with the provider, settings, or client state needed by later calls.
  - How: It calls `replace`, `ValueError`; uses time calculations.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: raises `ValueError`; may return `None` for not-found or unavailable data.
- `async create_event(request: CalendarEventRequest) -> CalendarEventResult`
  - Inputs: `request` (CalendarEventRequest)
  - Output: Returns `CalendarEventResult`.
  - Why: `GoogleCalendarClient.create_event` creates and persists a new domain object while enforcing idempotency and policy.
  - How: It calls `_event_result`, `self._request`, `_google_event_body`, `_path`, `_send_updates`.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async update_event(provider_event_id: str, request: CalendarEventRequest) -> CalendarEventResult`
  - Inputs: `provider_event_id` (str), `request` (CalendarEventRequest)
  - Output: Returns `CalendarEventResult`.
  - Why: `GoogleCalendarClient.update_event` provides the src/ghostrecon/services/calendar_adapters/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `_event_result`, `self._request`, `_google_event_body`, `_path`, `_send_updates`.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async cancel_event(provider_event_id: str, *, send_updates: bool = True) -> None`
  - Inputs: `provider_event_id` (str), `send_updates` (bool)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: `GoogleCalendarClient.cancel_event` provides the src/ghostrecon/services/calendar_adapters/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `self._request`, `_path`, `_send_updates`.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: may return `None` for not-found or unavailable data.
- `async get_availability(*, attendees: list[str], time_min: datetime, time_max: datetime, timezone: str) -> dict[str, list[CalendarBusySlot]]`
  - Inputs: `attendees` (list[str]), `time_min` (datetime), `time_max` (datetime), `timezone` (str)
  - Output: Returns `dict[str, list[CalendarBusySlot]]`.
  - Why: `GoogleCalendarClient.get_availability` loads one record or detail object for API or workflow callers.
  - How: It calls `calendars.items`, `self._request`, `isinstance`, `payload.get`, `calendar_payload.get`, `_parse_datetime`, `lower`, `slot.get`; uses parsing/normalization, time calculations.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async _request(method: str, path: str, *, params: dict[str, str] | None = None, json: dict[str, Any] | None = None) -> dict[str, Any]`
  - Inputs: `method` (str), `path` (str), `params` (dict[str, str] | None), `json` (dict[str, Any] | None)
  - Output: Returns `dict[str, Any]`.
  - Why: `GoogleCalendarClient._request` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `self._token`, `httpx.AsyncClient`, `response.json`, `client.request`, `CalendarProviderError`, `response.raise_for_status`, `_optional_int`, `get`; uses HTTP/provider IO.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
  - Failures: raises `CalendarProviderError`; catches provider or validation errors and maps them to the module contract.
- `async _token() -> str`
  - Inputs: No external inputs.
  - Output: Returns `str`.
  - Why: `GoogleCalendarClient._token` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `self._jwt_assertion`, `payload.get`, `httpx.AsyncClient`, `response.json`, `CalendarProviderError`, `datetime.now`, `timedelta`, `client.post`; uses HTTP/provider IO, time calculations.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
  - Failures: raises `CalendarProviderError`; catches provider or validation errors and maps them to the module contract.
- `_jwt_assertion() -> str`
  - Inputs: No external inputs.
  - Output: Returns `str`.
  - Why: `GoogleCalendarClient._jwt_assertion` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `serialization.load_pem_private_key`, `key.sign`, `time.time`, `_b64`, `encode`, `signing_input.encode`, `padding.PKCS1v15`, `hashes.SHA256`.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

#### Module Functions

##### `calendar_client_for_settings(settings: Settings) -> CalendarClient`

- Inputs: `settings` (Settings)
- Output: Returns `CalendarClient`.
- Why: `calendar_client_for_settings` provides the src/ghostrecon/services/calendar_adapters/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `GoogleCalendarClient`, `FakeCalendarClient`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_google_event_body(request: CalendarEventRequest) -> dict[str, Any]`

- Inputs: `request` (CalendarEventRequest)
- Output: Returns `dict[str, Any]`.
- Why: `_google_event_body` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_iso`, `lower`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_event_result(payload: dict[str, Any], calendar_id: str) -> CalendarEventResult`

- Inputs: `payload` (dict[str, Any]), `calendar_id` (str)
- Output: Returns `CalendarEventResult`.
- Why: `_event_result` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `payload.get`, `CalendarEventResult`, `CalendarProviderError`, `isinstance`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `CalendarProviderError`.

##### `_send_updates(send_updates: bool) -> str`

- Inputs: `send_updates` (bool)
- Output: Returns `str`.
- Why: `_send_updates` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_iso(value: datetime) -> str`

- Inputs: `value` (datetime)
- Output: Returns `str`.
- Why: `_iso` formats datetime values for API-safe JSON output.
- How: It calls `value.isoformat`, `value.replace`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_parse_datetime(value: object) -> datetime | None`

- Inputs: `value` (object)
- Output: Returns `datetime | None`; callers must handle the documented not-found or unavailable path.
- Why: `_parse_datetime` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `value.replace`, `isinstance`, `datetime.fromisoformat`, `parsed.replace`; uses parsing/normalization, time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data; catches provider or validation errors and maps them to the module contract.

##### `_path(value: str) -> str`

- Inputs: `value` (str)
- Output: Returns `str`.
- Why: `_path` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `quote`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_b64(value: bytes) -> str`

- Inputs: `value` (bytes)
- Output: Returns `str`.
- Why: `_b64` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `decode`, `rstrip`, `base64.urlsafe_b64encode`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_optional_int(value: object) -> int | None`

- Inputs: `value` (object)
- Output: Returns `int | None`; callers must handle the documented not-found or unavailable path.
- Why: `_optional_int` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data; catches provider or validation errors and maps them to the module contract.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_meeting.py`
- `tests/unit/test_calendar_adapters.py`

## Startup and dependency contract

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns database, Attio, and Google Calendar. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Database-owning APIs verify the migrated schema; configured provider checks are named without exposing credentials.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
