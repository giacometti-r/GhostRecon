
# crm-service Technical README

## Architecture

CRM Service is implemented by `src/ghostrecon/services/crm_exports.py`, `src/ghostrecon/services/crm_attio.py`. It is exposed through `crm_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | `POST` | `/v1/crm/sync/account` | `crm_sync_account` |
| service | `POST` | `/v1/crm/exports` | `crm_export_start` |
| service | `GET` | `/v1/crm/exports/{batch_id}` | `crm_export_detail` |
| service | `POST` | `/v1/crm/exports/{batch_id}/retry-failed` | `crm_export_retry_failed` |
| gateway | `POST` | `/v1/crm/exports` | `crm_export_start` |
| gateway | `GET` | `/v1/crm/exports/{batch_id}` | `crm_export_detail` |
| gateway | `POST` | `/v1/crm/exports/{batch_id}/retry-failed` | `crm_export_retry_failed` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.

## Function Reference

### `src/ghostrecon/services/crm_exports.py`

#### Classes

##### `PolicySkip`

`PolicySkip` is a data container or runtime class based on `ValueError`. Fields: none declared at class level.

#### Module Functions

##### `async start_crm_export(request: CrmExportCreateRequest, *, actor: str, idempotency_key: str, settings: Settings | None = None, client: CrmClient | None = None) -> CrmExportBatchOut`

- Inputs: `request` (CrmExportCreateRequest), `actor` (str), `idempotency_key` (str), `settings` (Settings | None), `client` (CrmClient | None)
- Output: Returns `CrmExportBatchOut`.
- Why: `start_crm_export` provides the src/ghostrecon/services/crm_exports.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_settings`, `session_scope`, `_unique_ordered`, `_require_exportable_targets`, `utcnow`, `CrmExportBatch`, `session.add`, `_ordered_targets`; uses database writes, idempotency lookup, outbox/event emission, serialization/projection, time calculations.
- Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_crm_export_batch(batch_id: str, *, settings: Settings | None = None) -> CrmExportBatchOut | None`

- Inputs: `batch_id` (str), `settings` (Settings | None)
- Output: Returns `CrmExportBatchOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `get_crm_export_batch` loads one record or detail object for API or workflow callers.
- How: It calls `session_scope`, `crm_export_batch_to_model`, `session.get`, `_batch_items`; uses database session queries, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async retry_failed_crm_export_items(batch_id: str, request: CrmExportRetryRequest | None = None, *, actor: str, idempotency_key: str, settings: Settings | None = None, client: CrmClient | None = None) -> CrmExportBatchOut | None`

- Inputs: `batch_id` (str), `request` (CrmExportRetryRequest | None), `actor` (str), `idempotency_key` (str), `settings` (Settings | None), `client` (CrmClient | None)
- Output: Returns `CrmExportBatchOut | None`; callers must handle the documented not-found or unavailable path.
- Why: `retry_failed_crm_export_items` requeues or reattempts previously failed work in a controlled way.
- How: It calls `get_settings`, `session_scope`, `process_crm_export_batch`, `session.get`, `_batch_items`, `crm_export_batch_to_model`, `utcnow`; uses database session queries, idempotency lookup, serialization/projection, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async process_crm_export_batch(batch_id: str, *, settings: Settings | None = None, client: CrmClient | None = None) -> CrmExportBatchOut`

- Inputs: `batch_id` (str), `settings` (Settings | None), `client` (CrmClient | None)
- Output: Returns `CrmExportBatchOut`.
- Why: `process_crm_export_batch` executes queued workflow work and records resulting state transitions.
- How: It calls `get_settings`, `AttioCrmClient`, `session_scope`, `_complete_batch`, `crm_export_batch_to_model`, `session.get`, `ValueError`, `_batch_items`; uses database session queries, idempotency lookup, outbox/event emission, policy validation, serialization/projection, time calculations.
- Side effects: adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`; catches provider or validation errors and maps them to the module contract.

##### `selection_hash(target_ids: list[str]) -> str`

- Inputs: `target_ids` (list[str])
- Output: Returns `str`.
- Why: `selection_hash` provides the src/ghostrecon/services/crm_exports.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `json.dumps`, `hexdigest`, `hashlib.sha256`, `payload.encode`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `crm_export_item_to_model(item: CrmExportItem) -> CrmExportItemOut`

- Inputs: `item` (CrmExportItem)
- Output: Returns `CrmExportItemOut`.
- Why: `crm_export_item_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `CrmExportItemOut`; uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `crm_export_batch_to_model(batch: CrmExportBatch, items: list[CrmExportItem]) -> CrmExportBatchOut`

- Inputs: `batch` (CrmExportBatch), `items` (list[CrmExportItem])
- Output: Returns `CrmExportBatchOut`.
- Why: `crm_export_batch_to_model` serializes a persisted ORM object into the API/model contract.
- How: It calls `CrmExportBatchOut`, `crm_export_item_to_model`; uses idempotency lookup, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _batch_by_idempotency_key(session: Any, idempotency_key: str) -> CrmExportBatch | None`

- Inputs: `session` (Any), `idempotency_key` (str)
- Output: Returns `CrmExportBatch | None`; callers must handle the documented not-found or unavailable path.
- Why: `_batch_by_idempotency_key` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session.scalar`, `where`, `select`; uses database session queries, idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async _batch_items(session: Any, batch_id: str) -> list[CrmExportItem]`

- Inputs: `session` (Any), `batch_id` (str)
- Output: Returns `list[CrmExportItem]`.
- Why: `_batch_items` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session.execute`, `result.scalars`, `order_by`, `where`, `select`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _load_targets(session: Any, target_ids: list[str]) -> dict[str, CrmTarget]`

- Inputs: `session` (Any), `target_ids` (list[str])
- Output: Returns `dict[str, CrmTarget]`.
- Why: `_load_targets` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `session.execute`, `where`, `result.scalars`, `in_`, `select`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_require_exportable_targets(target_ids: list[str], targets: dict[str, CrmTarget]) -> None`

- Inputs: `target_ids` (list[str]), `targets` (dict[str, CrmTarget])
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_require_exportable_targets` centralizes a validation gate and raises when the invariant is not satisfied.
- How: It calls `ValueError`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `ValueError`; may return `None` for not-found or unavailable data.

##### `_ordered_targets(targets: dict[str, CrmTarget]) -> list[CrmTarget]`

- Inputs: `targets` (dict[str, CrmTarget])
- Output: Returns `list[CrmTarget]`.
- Why: `_ordered_targets` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `targets.values`, `_target_order`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_target_order(target_type: str) -> int`

- Inputs: `target_type` (str)
- Output: Returns `int`.
- Why: `_target_order` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_normalize_target_type`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _create_item(session: Any, batch: CrmExportBatch, target: CrmTarget, settings: Settings) -> CrmExportItem`

- Inputs: `session` (Any), `batch` (CrmExportBatch), `target` (CrmTarget), `settings` (Settings)
- Output: Returns `CrmExportItem`.
- Why: `_create_item` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_new_item`, `_plan_for_target`, `_provider_object_for_type`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `_new_item(batch: CrmExportBatch, target: CrmTarget, provider_object: str, stable_match_key: str) -> CrmExportItem`

- Inputs: `batch` (CrmExportBatch), `target` (CrmTarget), `provider_object` (str), `stable_match_key` (str)
- Output: Returns `CrmExportItem`.
- Why: `_new_item` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `utcnow`, `CrmExportItem`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _plan_for_target(session: Any, target: CrmTarget, settings: Settings) -> CrmExportPlan`

- Inputs: `session` (Any), `target` (CrmTarget), `settings` (Settings)
- Output: Returns `CrmExportPlan`.
- Why: `_plan_for_target` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_normalize_target_type`, `ValueError`, `CrmExportPlan`, `session.get`, `PolicySkip`, `_person_plan`, `_iso`, `_lineage`; uses database session queries, parsing/normalization.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`, `PolicySkip`.

##### `async _person_plan(session: Any, target: CrmTarget, settings: Settings) -> CrmExportPlan`

- Inputs: `session` (Any), `target` (CrmTarget), `settings` (Settings)
- Output: Returns `CrmExportPlan`.
- Why: `_person_plan` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_normalize_target_type`, `CrmExportPlan`, `_lineage`, `session.get`, `ValueError`, `PolicySkip`, `email.lower`; uses database session queries, parsing/normalization, policy validation.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`, `PolicySkip`.

##### `_complete_batch(session: Any, batch: CrmExportBatch, items: list[CrmExportItem]) -> None`

- Inputs: `session` (Any), `batch` (CrmExportBatch), `items` (list[CrmExportItem])
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_complete_batch` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `utcnow`, `_counts`, `_batch_status`, `_enqueue_event`, `new_event`, `model_dump`, `crm_export_batch_to_model`, `sum`; uses idempotency lookup, outbox/event emission, serialization/projection, time calculations.
- Side effects: adds outbox/event records.
- Failures: may return `None` for not-found or unavailable data.

##### `_counts(items: list[CrmExportItem]) -> dict[str, object]`

- Inputs: `items` (list[CrmExportItem])
- Output: Returns `dict[str, object]`.
- Why: `_counts` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `counts.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_batch_status(items: list[CrmExportItem]) -> str`

- Inputs: `items` (list[CrmExportItem])
- Output: Returns `str`.
- Why: `_batch_status` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_mark_item_failure(item: CrmExportItem, message: str, *, retryable: bool, retry_after_seconds: int | None = None) -> None`

- Inputs: `item` (CrmExportItem), `message` (str), `retryable` (bool), `retry_after_seconds` (int | None)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_mark_item_failure` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `utcnow`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_enqueue_item_failed_event(session: Any, batch: CrmExportBatch, item: CrmExportItem) -> None`

- Inputs: `session` (Any), `batch` (CrmExportBatch), `item` (CrmExportItem)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `_enqueue_item_failed_event` creates an outbox event record for asynchronous consumers.
- How: It calls `_enqueue_event`, `new_event`, `model_dump`, `crm_export_item_to_model`; uses idempotency lookup, outbox/event emission, serialization/projection.
- Side effects: adds outbox/event records.
- Failures: may return `None` for not-found or unavailable data.

##### `_enqueue_event(session: Any, event: Any) -> OutboxEvent`

- Inputs: `session` (Any), `event` (Any)
- Output: Returns `OutboxEvent`.
- Why: `_enqueue_event` creates an outbox event record for asynchronous consumers.
- How: It calls `event.model_dump`, `OutboxEvent`, `session.add`; uses database writes, idempotency lookup, outbox/event emission, serialization/projection.
- Side effects: mutates database state; adds outbox/event records.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_normalize_target_type(target_type: str) -> str`

- Inputs: `target_type` (str)
- Output: Returns `str`.
- Why: `_normalize_target_type` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `aliases.get`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_provider_object_for_type(target_type: str) -> str`

- Inputs: `target_type` (str)
- Output: Returns `str`.
- Why: `_provider_object_for_type` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_normalize_target_type`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_unique_ordered(values: list[str]) -> list[str]`

- Inputs: `values` (list[str])
- Output: Returns `list[str]`.
- Why: `_unique_ordered` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `ordered.append`, `seen.add`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_lineage(target: CrmTarget) -> dict[str, object]`

- Inputs: `target` (CrmTarget)
- Output: Returns `dict[str, object]`.
- Why: `_lineage` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_iso(value: datetime | None) -> str | None`

- Inputs: `value` (datetime | None)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_iso` formats datetime values for API-safe JSON output.
- How: It calls `value.isoformat`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `utcnow() -> datetime`

- Inputs: No external inputs.
- Output: Returns `datetime`.
- Why: `utcnow` provides the src/ghostrecon/services/crm_exports.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `datetime.now`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

### `src/ghostrecon/services/crm_attio.py`

#### Classes

##### `CrmProviderError`

`CrmProviderError` is a data container or runtime class based on `RuntimeError`. Fields: none declared at class level.

- `__init__(message: str, *, retryable: bool = False, retry_after_seconds: int | None = None) -> None`
  - Inputs: `message` (str), `retryable` (bool), `retry_after_seconds` (int | None)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes CrmProviderError with the provider, settings, or client state needed by later calls.
  - How: It calls `__init__`, `super`.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.

##### `CrmExportPlan`

`CrmExportPlan` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `target_type` (str), `target_id` (str), `provider_object` (str), `stable_match_key` (str), `matching_attribute` (str), `values` (Mapping[str, Any]), `list_api_slug` (str | None), `list_entry_values` (Mapping[str, Any]).

##### `CrmSyncPlan`

`CrmSyncPlan` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `sync_type` (str), `target_id` (str), `provider_object` (str), `stable_match_key` (str), `matching_attribute` (str), `values` (Mapping[str, Any]), `list_api_slug` (str | None), `list_entry_values` (Mapping[str, Any]).

##### `CrmExportResult`

`CrmExportResult` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `provider_record_id` (str), `provider_list_id` (str | None), `provider_list_entry_id` (str | None), `raw_response` (Mapping[str, Any]).

##### `CrmClient`

`CrmClient` is a protocol/interface based on `Protocol`. Fields: none declared at class level.

- `async export(plan: CrmExportPlan) -> CrmExportResult`
  - Inputs: `plan` (CrmExportPlan)
  - Output: Returns `CrmExportResult`.
  - Why: `CrmClient.export` provides the src/ghostrecon/services/crm_attio.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async sync(plan: CrmSyncPlan) -> CrmExportResult`
  - Inputs: `plan` (CrmSyncPlan)
  - Output: Returns `CrmExportResult`.
  - Why: `CrmClient.sync` provides the src/ghostrecon/services/crm_attio.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `AttioClient`

`AttioClient` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `__init__(settings: Settings) -> None`
  - Inputs: `settings` (Settings)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes AttioClient with the provider, settings, or client state needed by later calls.
  - How: It calls `rstrip`, `ValueError`.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: raises `ValueError`; may return `None` for not-found or unavailable data.
- `async request(method: str, path: str, *, json: Mapping[str, Any] | None = None, params: Mapping[str, Any] | None = None) -> dict[str, Any]`
  - Inputs: `method` (str), `path` (str), `json` (Mapping[str, Any] | None), `params` (Mapping[str, Any] | None)
  - Output: Returns `dict[str, Any]`.
  - Why: `AttioClient.request` provides the src/ghostrecon/services/crm_attio.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `httpx.AsyncClient`, `response.json`, `client.request`, `_optional_int`, `CrmProviderError`, `response.raise_for_status`, `get`; uses HTTP/provider IO.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
  - Failures: raises `CrmProviderError`; catches provider or validation errors and maps them to the module contract.

##### `AttioCrmClient`

`AttioCrmClient` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `__init__(settings: Settings) -> None`
  - Inputs: `settings` (Settings)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes AttioCrmClient with the provider, settings, or client state needed by later calls.
  - How: It calls `AttioClient`.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.
- `async export(plan: CrmExportPlan) -> CrmExportResult`
  - Inputs: `plan` (CrmExportPlan)
  - Output: Returns `CrmExportResult`.
  - Why: `AttioCrmClient.export` provides the src/ghostrecon/services/crm_attio.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `self._upsert_plan`.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async sync(plan: CrmSyncPlan) -> CrmExportResult`
  - Inputs: `plan` (CrmSyncPlan)
  - Output: Returns `CrmExportResult`.
  - Why: `AttioCrmClient.sync` provides the src/ghostrecon/services/crm_attio.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `self._upsert_plan`.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async _upsert_plan(plan: CrmExportPlan | CrmSyncPlan) -> CrmExportResult`
  - Inputs: `plan` (CrmExportPlan | CrmSyncPlan)
  - Output: Returns `CrmExportResult`.
  - Why: `AttioCrmClient._upsert_plan` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `_record_id`, `CrmExportResult`, `request`, `_data`, `isinstance`, `data.get`, `_optional_str`, `entry_id_data.get`; uses parsing/normalization.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

#### Module Functions

##### `_data(payload: Mapping[str, Any]) -> Mapping[str, Any]`

- Inputs: `payload` (Mapping[str, Any])
- Output: Returns `Mapping[str, Any]`.
- Why: `_data` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `payload.get`, `isinstance`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_record_id(payload: Mapping[str, Any]) -> str`

- Inputs: `payload` (Mapping[str, Any])
- Output: Returns `str`.
- Why: `_record_id` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_data`, `data.get`, `isinstance`, `CrmProviderError`, `raw_id.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `CrmProviderError`.

##### `_optional_int(value: object) -> int | None`

- Inputs: `value` (object)
- Output: Returns `int | None`; callers must handle the documented not-found or unavailable path.
- Why: `_optional_int` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data; catches provider or validation errors and maps them to the module contract.

##### `_optional_str(value: object) -> str | None`

- Inputs: `value` (object)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_optional_str` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `isinstance`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_crm_exports.py`
