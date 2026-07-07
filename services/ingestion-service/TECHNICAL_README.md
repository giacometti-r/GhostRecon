
# ingestion-service Technical README

## Architecture

Ingestion Service is implemented by `src/ghostrecon/services/source_registry.py`, `src/ghostrecon/services/source_adapters.py`. It is exposed through `ingestion_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

Related/shared modules referenced by this service: `src/ghostrecon/service_apps/routers.py`.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | n/a | Source fetch worker | `fetch_source_by_id` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.

## Function Reference

### `src/ghostrecon/services/source_registry.py`

#### Classes

##### `SourceRegistryRepository`

`SourceRegistryRepository` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `__init__(session: AsyncSession) -> None`
  - Inputs: `session` (AsyncSession)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes SourceRegistryRepository with the provider, settings, or client state needed by later calls.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.
- `async list_source_health(kind: str | None = None) -> list[SourceHealth]`
  - Inputs: `kind` (str | None)
  - Output: Returns `list[SourceHealth]`.
  - Why: `SourceRegistryRepository.list_source_health` retrieves a bounded collection for API or workflow callers.
  - How: It calls `order_by`, `stmt.where`, `execute`, `source_health_from_definition`, `select`, `result.scalars`; uses database session queries.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async persist_fetched_item(source: SourceDefinition, fetched: FetchedSourceItem) -> tuple[RawSourceItem, bool]`
  - Inputs: `source` (SourceDefinition), `fetched` (FetchedSourceItem)
  - Output: Returns `tuple[RawSourceItem, bool]`.
  - Why: `SourceRegistryRepository.persist_fetched_item` provides the src/ghostrecon/services/source_registry.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `normalize_url`, `content_hash`, `build_raw_item_idempotency_key`, `classify_duplicate`, `RawSourceItem`, `add`, `scalar`, `execute`; uses database session queries, database writes, idempotency lookup, parsing/normalization, policy validation, time calculations.
  - Side effects: mutates database state; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `enqueue_event(event: Any) -> OutboxEvent`
  - Inputs: `event` (Any)
  - Output: Returns `OutboxEvent`.
  - Why: `SourceRegistryRepository.enqueue_event` provides the src/ghostrecon/services/source_registry.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `event.model_dump`, `OutboxEvent`, `add`; uses database writes, idempotency lookup, outbox/event emission, serialization/projection.
  - Side effects: mutates database state; adds outbox/event records.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

#### Module Functions

##### `utcnow() -> datetime`

- Inputs: No external inputs.
- Output: Returns `datetime`.
- Why: `utcnow` provides the src/ghostrecon/services/source_registry.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `datetime.now`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `normalize_url(url: str) -> str`

- Inputs: `url` (str)
- Output: Returns `str`.
- Why: `normalize_url` canonicalizes caller or provider input before comparison/persistence.
- How: It calls `urlsplit`, `lower`, `urlencode`, `urlunsplit`, `url.strip`, `parse_qsl`, `_is_tracking_param`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `content_hash(content: bytes | str) -> str`

- Inputs: `content` (bytes | str)
- Output: Returns `str`.
- Why: `content_hash` provides the src/ghostrecon/services/source_registry.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `hexdigest`, `isinstance`, `content.encode`, `hashlib.sha256`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `build_raw_item_idempotency_key(source_definition_id: str, external_id: str | None, canonical_url: str, item_content_hash: str) -> str`

- Inputs: `source_definition_id` (str), `external_id` (str | None), `canonical_url` (str), `item_content_hash` (str)
- Output: Returns `str`.
- Why: `build_raw_item_idempotency_key` derives a stable request, key, or projection object from richer inputs.
- How: It calls `hexdigest`, `hashlib.sha256`, `encode`; uses idempotency lookup.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `permitted_excerpt(content: str, storage_policy: str, *, max_chars: int = 500) -> str | None`

- Inputs: `content` (str), `storage_policy` (str), `max_chars` (int)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `permitted_excerpt` provides the src/ghostrecon/services/source_registry.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `re.sub`; uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `classify_duplicate(existing_content_hashes: set[str], item_content_hash: str) -> tuple[str, str | None]`

- Inputs: `existing_content_hashes` (set[str]), `item_content_hash` (str)
- Output: Returns `tuple[str, str | None]`; callers must handle the documented not-found or unavailable path.
- Why: `classify_duplicate` maps raw state into an internal classification used by callers.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `source_health_from_definition(source: SourceDefinition, now: datetime | None = None) -> SourceHealth`

- Inputs: `source` (SourceDefinition), `now` (datetime | None)
- Output: Returns `SourceHealth`.
- Why: `source_health_from_definition` provides the src/ghostrecon/services/source_registry.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_coerce_aware`, `SourceHealth`, `utcnow`, `max`, `total_seconds`; uses policy validation, time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async list_source_health(kind: str | None = None, settings: Settings | None = None) -> list[SourceHealth]`

- Inputs: `kind` (str | None), `settings` (Settings | None)
- Output: Returns `list[SourceHealth]`.
- Why: `list_source_health` retrieves a bounded collection for API or workflow callers.
- How: It calls `session_scope`, `SourceRegistryRepository`, `repository.list_source_health`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async fetch_source_by_id(source_definition_id: str, settings: Settings | None = None) -> dict[str, object]`

- Inputs: `source_definition_id` (str), `settings` (Settings | None)
- Output: Returns `dict[str, object]`.
- Why: `fetch_source_by_id` retrieves external or registered source data.
- How: It calls `session_scope`, `SourceRegistryRepository`, `utcnow`, `create_adapter`, `session.get`, `ValueError`, `repository.enqueue_event`, `adapter.fetch`; uses database session queries, idempotency lookup, outbox/event emission, parsing/normalization, time calculations.
- Side effects: adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError`; catches provider or validation errors and maps them to the module contract.

##### `_is_tracking_param(key: str) -> bool`

- Inputs: `key` (str)
- Output: Returns `bool`.
- Why: `_is_tracking_param` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `key.lower`, `lowered.startswith`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_coerce_aware(value: datetime | None) -> datetime | None`

- Inputs: `value` (datetime | None)
- Output: Returns `datetime | None`; callers must handle the documented not-found or unavailable path.
- Why: `_coerce_aware` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `value.replace`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_metadata_without_body(metadata: dict[str, object]) -> dict[str, object]`

- Inputs: `metadata` (dict[str, object])
- Output: Returns `dict[str, object]`.
- Why: `_metadata_without_body` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `metadata.items`, `key.lower`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

### `src/ghostrecon/services/source_adapters.py`

#### Classes

##### `FetchedSourceItem`

`FetchedSourceItem` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `url` (str), `content` (str), `external_id` (str | None), `published_at` (datetime | None), `original_language` (str | None), `source_timezone` (str | None), `metadata` (dict[str, object]).

##### `SourceAdapter`

`SourceAdapter` is a protocol/interface based on `Protocol`. Fields: none declared at class level.

- `async fetch(source: SourceDefinition) -> list[FetchedSourceItem]`
  - Inputs: `source` (SourceDefinition)
  - Output: Returns `list[FetchedSourceItem]`.
  - Why: `SourceAdapter.fetch` provides the src/ghostrecon/services/source_adapters.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It uses parsing/normalization.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `HttpPageAdapter`

`HttpPageAdapter` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `async fetch(source: SourceDefinition) -> list[FetchedSourceItem]`
  - Inputs: `source` (SourceDefinition)
  - Output: Returns `list[FetchedSourceItem]`.
  - Why: `HttpPageAdapter.fetch` provides the src/ghostrecon/services/source_adapters.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `httpx.AsyncClient`, `response.raise_for_status`, `parse_http_page`, `client.get`; uses HTTP/provider IO, parsing/normalization.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `SchemaOrgAdapter`

`SchemaOrgAdapter` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `async fetch(source: SourceDefinition) -> list[FetchedSourceItem]`
  - Inputs: `source` (SourceDefinition)
  - Output: Returns `list[FetchedSourceItem]`.
  - Why: `SchemaOrgAdapter.fetch` provides the src/ghostrecon/services/source_adapters.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `parse_schema_org_events`, `httpx.AsyncClient`, `response.raise_for_status`, `client.get`; uses HTTP/provider IO, parsing/normalization.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `IcsAdapter`

`IcsAdapter` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `async fetch(source: SourceDefinition) -> list[FetchedSourceItem]`
  - Inputs: `source` (SourceDefinition)
  - Output: Returns `list[FetchedSourceItem]`.
  - Why: `IcsAdapter.fetch` provides the src/ghostrecon/services/source_adapters.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `parse_ics_events`, `httpx.AsyncClient`, `response.raise_for_status`, `client.get`; uses HTTP/provider IO, parsing/normalization.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `RssAtomAdapter`

`RssAtomAdapter` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `async fetch(source: SourceDefinition) -> list[FetchedSourceItem]`
  - Inputs: `source` (SourceDefinition)
  - Output: Returns `list[FetchedSourceItem]`.
  - Why: `RssAtomAdapter.fetch` provides the src/ghostrecon/services/source_adapters.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `parse_rss_atom`, `httpx.AsyncClient`, `response.raise_for_status`, `client.get`; uses HTTP/provider IO, parsing/normalization.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `ScheduledQueryAdapter`

`ScheduledQueryAdapter` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `async fetch(source: SourceDefinition) -> list[FetchedSourceItem]`
  - Inputs: `source` (SourceDefinition)
  - Output: Returns `list[FetchedSourceItem]`.
  - Why: `ScheduledQueryAdapter.fetch` provides the src/ghostrecon/services/source_adapters.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `get`, `isinstance`, `httpx.AsyncClient`, `response.raise_for_status`, `FetchedSourceItem`, `client.get`, `urlencode`; uses HTTP/provider IO.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `GdeltDocAdapter`

`GdeltDocAdapter` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `async fetch(source: SourceDefinition) -> list[FetchedSourceItem]`
  - Inputs: `source` (SourceDefinition)
  - Output: Returns `list[FetchedSourceItem]`.
  - Why: `GdeltDocAdapter.fetch` provides the src/ghostrecon/services/source_adapters.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `get`, `isinstance`, `parse_gdelt_doc_articles`, `params.update`, `httpx.AsyncClient`, `response.raise_for_status`, `client.get`; uses HTTP/provider IO, parsing/normalization.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

#### Module Functions

##### `create_adapter(adapter_type: str) -> SourceAdapter`

- Inputs: `adapter_type` (str)
- Output: Returns `SourceAdapter`.
- Why: `create_adapter` creates and persists a new domain object while enforcing idempotency and policy.
- How: It calls `HttpPageAdapter`, `SchemaOrgAdapter`, `IcsAdapter`, `RssAtomAdapter`, `ScheduledQueryAdapter`, `GdeltDocAdapter`, `ValueError`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `ValueError`; catches provider or validation errors and maps them to the module contract.

##### `parse_http_page(html: str, url: str, language: str | None = None) -> FetchedSourceItem`

- Inputs: `html` (str), `url` (str), `language` (str | None)
- Output: Returns `FetchedSourceItem`.
- Why: `parse_http_page` converts raw external content into normalized internal objects.
- How: It calls `re.search`, `FetchedSourceItem`, `_compact_html_text`, `join`, `title_match.group`, `unescape`, `description_match.group`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `parse_schema_org_events(html: str, page_url: str, language: str | None = None) -> list[FetchedSourceItem]`

- Inputs: `html` (str), `page_url` (str), `language` (str | None)
- Output: Returns `list[FetchedSourceItem]`.
- Why: `parse_schema_org_events` converts raw external content into normalized internal objects.
- How: It calls `re.findall`, `_iter_jsonld_nodes`, `json.loads`, `event.get`, `join`, `items.append`, `isinstance`, `FetchedSourceItem`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `parse_ics_events(ics_text: str, calendar_url: str, language: str | None = None) -> list[FetchedSourceItem]`

- Inputs: `ics_text` (str), `calendar_url` (str), `language` (str | None)
- Output: Returns `list[FetchedSourceItem]`.
- Why: `parse_ics_events` converts raw external content into normalized internal objects.
- How: It calls `_unfold_ics_lines`, `ics_text.splitlines`, `line.split`, `upper`, `value.strip`, `join`, `parsed.append`, `event.get`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `parse_rss_atom(feed_text: str, feed_url: str, language: str | None = None) -> list[FetchedSourceItem]`

- Inputs: `feed_text` (str), `feed_url` (str), `language` (str | None)
- Output: Returns `list[FetchedSourceItem]`.
- Why: `parse_rss_atom` converts raw external content into normalized internal objects.
- How: It calls `ET.fromstring`, `_child_text`, `items.append`, `root.findall`, `_link_href`, `FetchedSourceItem`, `root.iter`, `_local_name`; uses parsing/normalization, time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `parse_gdelt_doc_articles(payload_text: str, query_url: str, language: str | None = None) -> list[FetchedSourceItem]`

- Inputs: `payload_text` (str), `query_url` (str), `language` (str | None)
- Output: Returns `list[FetchedSourceItem]`.
- Why: `parse_gdelt_doc_articles` converts raw external content into normalized internal objects.
- How: It calls `payload.get`, `json.loads`, `isinstance`, `_parse_feed_datetime`, `items.append`, `FetchedSourceItem`, `article.get`, `join`; uses parsing/normalization, time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `_iter_jsonld_nodes(payload: object) -> Iterable[dict[str, object]]`

- Inputs: `payload` (object)
- Output: Returns `Iterable[dict[str, object]]`.
- Why: `_iter_jsonld_nodes` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `isinstance`, `payload.get`, `_iter_jsonld_nodes`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_unfold_ics_lines(lines: list[str]) -> list[str]`

- Inputs: `lines` (list[str])
- Output: Returns `list[str]`.
- Why: `_unfold_ics_lines` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `line.startswith`, `unfolded.append`, `line.strip`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_child_text(element: ET.Element, names: set[str]) -> str | None`

- Inputs: `element` (ET.Element), `names` (set[str])
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_child_text` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_local_name`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_link_href(element: ET.Element) -> str | None`

- Inputs: `element` (ET.Element)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_link_href` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_local_name`, `get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_local_name(tag: str) -> str`

- Inputs: `tag` (str)
- Output: Returns `str`.
- Why: `_local_name` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `tag.rsplit`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_parse_feed_datetime(value: str | None) -> datetime | None`

- Inputs: `value` (str | None)
- Output: Returns `datetime | None`; callers must handle the documented not-found or unavailable path.
- Why: `_parse_feed_datetime` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `parsedate_to_datetime`, `datetime.fromisoformat`, `value.replace`; uses parsing/normalization, time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data; catches provider or validation errors and maps them to the module contract.

##### `_compact_html_text(value: str) -> str`

- Inputs: `value` (str)
- Output: Returns `str`.
- Why: `_compact_html_text` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `re.sub`, `unescape`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

## Shared Module Notes

- `src/ghostrecon/service_apps/routers.py` is shared or mounted behavior used by this service; its exhaustive function reference lives in the service that owns that module in the mapping, or in `gateway-service` for route/factory code.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_source_registry.py`
- `tests/unit/test_source_adapters.py`
- `tests/unit/test_attio_signature.py`
