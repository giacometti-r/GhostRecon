
# event-intelligence-service Technical README

## Architecture

Event Intelligence Service is implemented by `src/ghostrecon/services/event_intelligence/`. It is exposed through `event_intelligence_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

Related/shared modules referenced by this service: `src/ghostrecon/services/source_adapters.py`, `src/ghostrecon/services/source_registry.py`.

Geocoding support is implemented by `src/ghostrecon/services/geocoding.py`. Production deployments use a Nominatim-compatible structured search adapter; local demo runs use deterministic stored venue coordinates.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | `GET` | `/v1/intelligence/sources/health` | `source_health` |
| service | `GET` | `/v1/intelligence/events` | `intelligence_events` |
| service | `POST` | `/v1/intelligence/events/manual` | `intelligence_create_manual_event` |
| service | `PATCH` | `/v1/intelligence/events/{event_id}` | `intelligence_patch_event` |
| service | `GET` | `/v1/intelligence/events/{event_id}` | `intelligence_event_detail` |
| service | `GET` | `/v1/intelligence/events/{event_id}/participants` | `intelligence_event_participants` |
| service | `GET` | `/v1/intelligence/participants` | `intelligence_participants` |
| gateway | `GET` | `/v1/intelligence/sources/health` | `source_health` |
| gateway | `GET` | `/v1/intelligence/events` | `intelligence_events` |
| gateway | `POST` | `/v1/intelligence/events/manual` | `intelligence_create_manual_event` |
| gateway | `PATCH` | `/v1/intelligence/events/{event_id}` | `intelligence_patch_event` |
| gateway | `GET` | `/v1/intelligence/events/{event_id}` | `intelligence_event_detail` |
| gateway | `GET` | `/v1/intelligence/events/{event_id}/participants` | `intelligence_event_participants` |
| gateway | `GET` | `/v1/intelligence/participants` | `intelligence_participants` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.
- Event formats are persisted as `in-person`, `online`, `hybrid`, or `unknown`; request/filter aliases `physical` and `virtual` normalize to the canonical values.
- Manual event creation and event patching are idempotent, version-aware where mutable, and persist address/geocoding status without blocking on geocoder failures.

## Function Reference

### `src/ghostrecon/services/event_intelligence/`

#### Classes

##### `NormalizedTime`

`NormalizedTime` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `original_value` (str | None), `source_timezone` (str | None), `iana_timezone` (str | None), `value_utc` (datetime | None), `status` (str).

##### `EventCandidate`

`EventCandidate` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `name` (str), `event_series_key` (str), `external_id` (str | None), `canonical_url` (str | None), `original_start` (str | None), `original_end` (str | None), `source_timezone` (str | None), `iana_timezone` (str | None), `timezone_status` (str), `starts_at_utc` (datetime | None), `ends_at_utc` (datetime | None), `event_format` (str), `venue_name` (str | None), `street_address` (str | None), `city` (str | None), `region` (str | None), `postcode` (str | None), `country` (str | None), `latitude` (float | None), `longitude` (float | None), `geocode_status` (str | None), `geocode_provider` (str | None), `geocode_display_name` (str | None), `geocoded_at` (datetime | None), `virtual_url` (str | None), `topics` (list[object]), `organizers` (list[object]), `confidence` (int), `canonical_state` (str).

##### `ParticipantCandidate`

`ParticipantCandidate` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `published_name` (str), `source_participant_id` (str | None), `organization` (str | None), `published_role` (str | None), `participant_type` (str), `profile_url` (str | None), `resolution_confidence` (int).

##### `EventIntelligenceRepository`

`EventIntelligenceRepository` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `__init__(session: AsyncSession) -> None`
  - Inputs: `session` (AsyncSession)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes EventIntelligenceRepository with the provider, settings, or client state needed by later calls.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.
- `async parse_pending_items(source_definition_id: str | None = None) -> dict[str, object]`
  - Inputs: `source_definition_id` (str | None)
  - Output: Returns `dict[str, object]`.
  - Why: `EventIntelligenceRepository.parse_pending_items` converts raw external content into normalized internal objects.
  - How: It calls `order_by`, `result.all`, `stmt.where`, `execute`, `where`, `candidates_from_raw_item`, `participants_from_raw_item`, `self.upsert_event`; uses database session queries, parsing/normalization.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: catches provider or validation errors and maps them to the module contract.
- `async upsert_event(source: SourceDefinition, raw_item: RawSourceItem, candidate: EventCandidate) -> tuple[CyberEvent, bool]`
  - Inputs: `source` (SourceDefinition), `raw_item` (RawSourceItem), `candidate` (EventCandidate)
  - Output: Returns `tuple[CyberEvent, bool]`.
  - Why: `EventIntelligenceRepository.upsert_event` provides the src/ghostrecon/services/event_intelligence/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `build_event_dedupe_key`, `CyberEvent`, `add`, `self._enqueue_event`, `scalar`, `flush`, `new_event`, `where`; uses database session queries, database writes, idempotency lookup, outbox/event emission.
  - Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async upsert_participant(source: SourceDefinition, raw_item: RawSourceItem, event: CyberEvent, candidate: ParticipantCandidate) -> tuple[EventParticipant, bool]`
  - Inputs: `source` (SourceDefinition), `raw_item` (RawSourceItem), `event` (CyberEvent), `candidate` (ParticipantCandidate)
  - Output: Returns `tuple[EventParticipant, bool]`.
  - Why: `EventIntelligenceRepository.upsert_participant` provides the src/ghostrecon/services/event_intelligence/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `build_participant_dedupe_key`, `participant_eligibility`, `EventParticipant`, `add`, `self._enqueue_event`, `scalar`, `flush`, `new_event`; uses database session queries, database writes, idempotency lookup, outbox/event emission, policy validation.
  - Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async list_events(*, series: str | None, source: str | None, country: str | None, event_format: str | None, limit: int) -> list[CyberEvent]`
  - Inputs: `series` (str | None), `source` (str | None), `country` (str | None), `event_format` (str | None), `limit` (int)
  - Output: Returns `list[CyberEvent]`.
  - Why: `EventIntelligenceRepository.list_events` retrieves a bounded collection for API or workflow callers.
  - How: It calls `limit`, `stmt.where`, `execute`, `result.scalars`, `order_by`, `country.upper`, `select`; uses database session queries.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async list_participants(*, event_id: str | None, reuse_state: str | None, limit: int) -> list[EventParticipant]`
  - Inputs: `event_id` (str | None), `reuse_state` (str | None), `limit` (int)
  - Output: Returns `list[EventParticipant]`.
  - Why: `EventIntelligenceRepository.list_participants` retrieves a bounded collection for API or workflow callers.
  - How: It calls `limit`, `stmt.where`, `execute`, `result.scalars`, `order_by`, `select`; uses database session queries.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `_enqueue_event(event: Any) -> OutboxEvent`
  - Inputs: `event` (Any)
  - Output: Returns `OutboxEvent`.
  - Why: `EventIntelligenceRepository._enqueue_event` creates an outbox event record for asynchronous consumers.
  - How: It calls `event.model_dump`, `OutboxEvent`, `add`; uses database writes, idempotency lookup, outbox/event emission, serialization/projection.
  - Side effects: mutates database state; adds outbox/event records.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

#### Module Functions

##### `normalize_event_time(value: str | None, timezone_hint: str | None) -> NormalizedTime`

- Inputs: `value` (str | None), `timezone_hint` (str | None)
- Output: Returns `NormalizedTime`.
- Why: `normalize_event_time` canonicalizes caller or provider input before comparison/persistence.
- How: It calls `_parse_datetime`, `_is_ambiguous_local_time`, `NormalizedTime`, `ZoneInfo`, `astimezone`, `parsed.astimezone`, `_zone_key`, `parsed.replace`; uses parsing/normalization, time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `build_event_dedupe_key(candidate: EventCandidate) -> str`

- Inputs: `candidate` (EventCandidate)
- Output: Returns `str`.
- Why: `build_event_dedupe_key` derives a stable request, key, or projection object from richer inputs.
- How: It calls `join`, `isoformat`, `hexdigest`, `_slug`, `date`, `hashlib.sha256`, `identity.encode`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `build_participant_dedupe_key(event_id: str, candidate: ParticipantCandidate) -> str`

- Inputs: `event_id` (str), `candidate` (ParticipantCandidate)
- Output: Returns `str`.
- Why: `build_participant_dedupe_key` derives a stable request, key, or projection object from richer inputs.
- How: It calls `join`, `hexdigest`, `normalize_url`, `_slug`, `hashlib.sha256`, `identity.encode`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `participant_eligibility(reuse_state: str) -> tuple[bool, bool]`

- Inputs: `reuse_state` (str)
- Output: Returns `tuple[bool, bool]`.
- Why: `participant_eligibility` provides the src/ghostrecon/services/event_intelligence/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `candidates_from_raw_item(source: SourceDefinition, raw_item: RawSourceItem) -> list[EventCandidate]`

- Inputs: `source` (SourceDefinition), `raw_item` (RawSourceItem)
- Output: Returns `list[EventCandidate]`.
- Why: `candidates_from_raw_item` provides the src/ghostrecon/services/event_intelligence/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `isinstance`, `metadata.get`, `_candidate_from_page`, `get`, `_slug`, `_candidate_from_schema_org`, `_candidate_from_ics`, `_candidate_from_feed`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `participants_from_raw_item(source: SourceDefinition, raw_item: RawSourceItem) -> list[ParticipantCandidate]`

- Inputs: `source` (SourceDefinition), `raw_item` (RawSourceItem)
- Output: Returns `list[ParticipantCandidate]`.
- Why: `participants_from_raw_item` provides the src/ghostrecon/services/event_intelligence/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `metadata.get`, `isinstance`, `_as_list`, `schema_event.get`, `_participant_from_schema_node`, `participants.append`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async fetch_event_source(source_definition_id: str, settings: Settings | None = None) -> dict[str, object]`

- Inputs: `source_definition_id` (str), `settings` (Settings | None)
- Output: Returns `dict[str, object]`.
- Why: `fetch_event_source` retrieves external or registered source data.
- How: It calls `fetch_source_by_id`, `parse_pending_event_items`; uses parsing/normalization.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async parse_pending_event_items(source_definition_id: str | None = None, settings: Settings | None = None) -> dict[str, object]`

- Inputs: `source_definition_id` (str | None), `settings` (Settings | None)
- Output: Returns `dict[str, object]`.
- Why: `parse_pending_event_items` converts raw external content into normalized internal objects.
- How: It calls `session_scope`, `EventIntelligenceRepository`, `repository.parse_pending_items`; uses parsing/normalization.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async list_events(*, series: str | None = None, source: str | None = None, country: str | None = None, event_format: str | None = None, limit: int = 100, settings: Settings | None = None) -> list[CyberEvent]`

- Inputs: `series` (str | None), `source` (str | None), `country` (str | None), `event_format` (str | None), `limit` (int), `settings` (Settings | None)
- Output: Returns `list[CyberEvent]`.
- Why: `list_events` retrieves a bounded collection for API or workflow callers.
- How: It calls `session_scope`, `EventIntelligenceRepository`, `repository.list_events`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_event(event_id: str, settings: Settings | None = None) -> CyberEvent | None`

- Inputs: `event_id` (str), `settings` (Settings | None)
- Output: Returns `CyberEvent | None`; callers must handle the documented not-found or unavailable path.
- Why: `get_event` loads one record or detail object for API or workflow callers.
- How: It calls `session_scope`, `session.get`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async list_participants(*, event_id: str | None = None, reuse_state: str | None = None, limit: int = 100, settings: Settings | None = None) -> list[EventParticipant]`

- Inputs: `event_id` (str | None), `reuse_state` (str | None), `limit` (int), `settings` (Settings | None)
- Output: Returns `list[EventParticipant]`.
- Why: `list_participants` retrieves a bounded collection for API or workflow callers.
- How: It calls `session_scope`, `EventIntelligenceRepository`, `repository.list_participants`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `event_to_api(event: CyberEvent) -> dict[str, object]`

- Inputs: `event` (CyberEvent)
- Output: Returns `dict[str, object]`.
- Why: `event_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async create_manual_event(request: ManualEventCreate, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> CyberEvent`

- Inputs: `request` (ManualEventCreate), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `CyberEvent`.
- Why: `create_manual_event` creates an operator-supplied event, resolves optional address coordinates, and preserves source-item lineage.
- How: It validates the address/format contract, runs the configured geocoder, writes the event, and records audit/outbox events under the idempotency key.
- Side effects: mutates database state; may call a configured geocoder.
- Failures: raises `ValueError` for invalid workflow input.

##### `async update_event(event_id: str, request: EventUpdateRequest, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> CyberEvent | None`

- Inputs: `event_id` (str), `request` (EventUpdateRequest), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `CyberEvent | None`.
- Why: `update_event` applies version-aware event edits from the dashboard/API.
- How: It checks the optimistic version, patches mutable fields, re-geocodes when address inputs change, increments version, and records audit/outbox events.
- Side effects: mutates database state; may call a configured geocoder.
- Failures: raises `ValueError` for version conflicts or invalid workflow input; may return `None` for missing events.

##### `participant_to_api(participant: EventParticipant) -> dict[str, object]`

- Inputs: `participant` (EventParticipant)
- Output: Returns `dict[str, object]`.
- Why: `participant_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_candidate_from_schema_org(event: dict[str, object], source: SourceDefinition, raw_item: RawSourceItem, series: str, timezone_hint: str | None) -> EventCandidate`

- Inputs: `event` (dict[str, object]), `source` (SourceDefinition), `raw_item` (RawSourceItem), `series` (str), `timezone_hint` (str | None)
- Output: Returns `EventCandidate`.
- Why: `_candidate_from_schema_org` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_string`, `normalize_event_time`, `EventCandidate`, `event.get`, `isinstance`, `location.get`, `normalize_url`, `_format_from_schema`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_candidate_from_ics(event: dict[str, object], source: SourceDefinition, raw_item: RawSourceItem, series: str, timezone_hint: str | None) -> EventCandidate`

- Inputs: `event` (dict[str, object]), `source` (SourceDefinition), `raw_item` (RawSourceItem), `series` (str), `timezone_hint` (str | None)
- Output: Returns `EventCandidate`.
- Why: `_candidate_from_ics` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_string`, `normalize_event_time`, `EventCandidate`, `event.get`, `_ics_datetime`, `normalize_url`, `startswith`, `location.lower`; uses parsing/normalization, time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_candidate_from_feed(metadata: dict[str, object], source: SourceDefinition, raw_item: RawSourceItem, series: str, timezone_hint: str | None) -> EventCandidate`

- Inputs: `metadata` (dict[str, object]), `source` (SourceDefinition), `raw_item` (RawSourceItem), `series` (str), `timezone_hint` (str | None)
- Output: Returns `EventCandidate`.
- Why: `_candidate_from_feed` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `EventCandidate`, `normalize_event_time`, `isoformat`, `_string`, `metadata.get`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_candidate_from_page(metadata: dict[str, object], source: SourceDefinition, raw_item: RawSourceItem, series: str, timezone_hint: str | None) -> EventCandidate`

- Inputs: `metadata` (dict[str, object]), `source` (SourceDefinition), `raw_item` (RawSourceItem), `series` (str), `timezone_hint` (str | None)
- Output: Returns `EventCandidate`.
- Why: `_candidate_from_page` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `EventCandidate`, `_string`, `metadata.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_participant_from_schema_node(item: object, participant_type: str) -> ParticipantCandidate | None`

- Inputs: `item` (object), `participant_type` (str)
- Output: Returns `ParticipantCandidate | None`; callers must handle the documented not-found or unavailable path.
- Why: `_participant_from_schema_node` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `isinstance`, `_string`, `item.get`, `ParticipantCandidate`, `item.strip`, `affiliation.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_parse_datetime(value: str) -> datetime | None`

- Inputs: `value` (str)
- Output: Returns `datetime | None`; callers must handle the documented not-found or unavailable path.
- Why: `_parse_datetime` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `value.strip`, `re.fullmatch`, `date`, `datetime.combine`, `replace`, `datetime.strptime`, `datetime.fromisoformat`, `compact.replace`; uses parsing/normalization, time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data; catches provider or validation errors and maps them to the module contract.

##### `_ics_datetime(value: str | None) -> str | None`

- Inputs: `value` (str | None)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_ics_datetime` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `value.strip`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_is_ambiguous_local_time(value: datetime, zone: ZoneInfo) -> bool`

- Inputs: `value` (datetime), `zone` (ZoneInfo)
- Output: Returns `bool`.
- Why: `_is_ambiguous_local_time` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `utcoffset`, `value.replace`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_format_from_schema(attendance_mode: str | None) -> str`

- Inputs: `attendance_mode` (str | None)
- Output: Returns `str`.
- Why: `_format_from_schema` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `attendance_mode.lower`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_as_list(value: object) -> list[object]`

- Inputs: `value` (object)
- Output: Returns `list[object]`.
- Why: `_as_list` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `isinstance`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_keywords(value: object) -> list[object]`

- Inputs: `value` (object)
- Output: Returns `list[object]`.
- Why: `_keywords` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `isinstance`, `part.strip`, `value.split`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_compact_org(item: object) -> object`

- Inputs: `item` (object)
- Output: Returns `object`.
- Why: `_compact_org` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `isinstance`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_country_code(value: object) -> str | None`

- Inputs: `value` (object)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_country_code` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_string`, `text.upper`, `upper`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_string(value: object) -> str | None`

- Inputs: `value` (object)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_string` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `isinstance`, `_string`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_slug(value: str) -> str`

- Inputs: `value` (str)
- Output: Returns `str`.
- Why: `_slug` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `re.sub`, `value.lower`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_zone_key(value: object) -> str | None`

- Inputs: `value` (object)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_zone_key` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `getattr`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

## Shared Module Notes

- `src/ghostrecon/services/source_adapters.py` is shared or mounted behavior used by this service; its exhaustive function reference lives in the service that owns that module in the mapping, or in `gateway-service` for route/factory code.
- `src/ghostrecon/services/source_registry.py` is shared or mounted behavior used by this service; its exhaustive function reference lives in the service that owns that module in the mapping, or in `gateway-service` for route/factory code.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_event_intelligence.py`
- `tests/unit/test_event_routes.py`
- `tests/unit/test_source_adapters.py`
- `tests/unit/test_source_registry.py`

## Shared Sprint 25a Security Perimeter

This service inherits correlation, transport bounds, security response headers, and strict-profile
reserved-header rejection from `create_base_app`. These behaviors are not owner-service
authentication or authorization. Direct-service restrictions, workload/OBO verification, complete
operation classification, database context installation, and active RLS remain Sprint 25b work. See
the [security foundation reference](../../docs/security-foundation.md).

## Startup and dependency contract

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns database; live Nominatim geocoder and an identifying user agent. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Database-owning APIs verify the migrated schema; configured provider checks are named without exposing credentials.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
