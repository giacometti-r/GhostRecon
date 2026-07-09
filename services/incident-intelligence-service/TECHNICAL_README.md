
# incident-intelligence-service Technical README

## Architecture

Incident Intelligence Service is implemented by `src/ghostrecon/services/incident_intelligence.py`, `src/ghostrecon/services/security_feeds.py`. It is exposed through `incident_intelligence_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

Related/shared modules referenced by this service: `src/ghostrecon/services/source_registry.py`.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | `GET` | `/v1/intelligence/incidents` | `intelligence_incidents` |
| service | `POST` | `/v1/intelligence/incidents/manual` | `intelligence_create_manual_incident` |
| service | `GET` | `/v1/intelligence/incidents/{incident_id}` | `intelligence_incident_detail` |
| service | `GET` | `/v1/intelligence/watch-targets` | `intelligence_watch_targets` |
| service | `POST` | `/v1/intelligence/watch-targets` | `intelligence_create_watch_target` |
| service | `PATCH` | `/v1/intelligence/watch-targets/{watch_target_id}` | `intelligence_patch_watch_target` |
| service | `POST` | `/v1/intelligence/incidents/{incident_id}/promote-to-watchlist` | `intelligence_promote_incident_to_watchlist` |
| gateway | `GET` | `/v1/intelligence/incidents` | `intelligence_incidents` |
| gateway | `POST` | `/v1/intelligence/incidents/manual` | `intelligence_create_manual_incident` |
| gateway | `GET` | `/v1/intelligence/incidents/{incident_id}` | `intelligence_incident_detail` |
| gateway | `GET` | `/v1/intelligence/watch-targets` | `intelligence_watch_targets` |
| gateway | `POST` | `/v1/intelligence/watch-targets` | `intelligence_create_watch_target` |
| gateway | `PATCH` | `/v1/intelligence/watch-targets/{watch_target_id}` | `intelligence_patch_watch_target` |
| gateway | `POST` | `/v1/intelligence/incidents/{incident_id}/promote-to-watchlist` | `intelligence_promote_incident_to_watchlist` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.
- Incident candidates and manual incident requests are split into company/domain-scoped rows with a shared `incident_group_key`.
- Incident watch promotion requires an optimistic version match and `status=corroborated`, and creates actor-owned `company` watch targets.

## Function Reference

### `src/ghostrecon/services/incident_intelligence.py`

#### Classes

##### `ArticleCandidate`

`ArticleCandidate` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `canonical_url` (str), `publisher` (str | None), `title` (str), `permitted_excerpt` (str | None), `published_at` (datetime | None), `retrieved_at` (datetime | None), `original_language` (str | None), `translated_title` (str | None), `translation_metadata` (dict[str, object]), `content_hash` (str), `syndication_cluster_key` (str), `dedupe_key` (str).

##### `IncidentCandidate`

`IncidentCandidate` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `title` (str), `affected_companies` (list[object]), `affected_domains` (list[object]), `incident_type` (str | None), `attack_vector` (str | None), `first_observed_at` (datetime | None), `last_observed_at` (datetime | None), `geography` (list[object]), `languages` (list[object]), `confidence` (int), `dedupe_key` (str), `evidence_family_key` (str), `authoritative` (bool), `incident_group_key` (str | None), `primary_affected_company` (str | None), `primary_affected_domain` (str | None), `evidence_urls` (list[object]).

##### `IncidentIntelligenceRepository`

`IncidentIntelligenceRepository` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `__init__(session: AsyncSession) -> None`
  - Inputs: `session` (AsyncSession)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes IncidentIntelligenceRepository with the provider, settings, or client state needed by later calls.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.
- `async parse_pending_items(source_definition_id: str | None = None) -> dict[str, object]`
  - Inputs: `source_definition_id` (str | None)
  - Output: Returns `dict[str, object]`.
  - Why: `IncidentIntelligenceRepository.parse_pending_items` converts raw external content into normalized internal objects.
  - How: It calls `order_by`, `result.all`, `stmt.where`, `execute`, `where`, `article_candidate_from_raw_item`, `incident_candidate_from_article`, `self.upsert_article`; uses database session queries, parsing/normalization.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: catches provider or validation errors and maps them to the module contract.
- `async upsert_article(source: SourceDefinition, raw_item: RawSourceItem, candidate: ArticleCandidate) -> tuple[NewsArticle, bool]`
  - Inputs: `source` (SourceDefinition), `raw_item` (RawSourceItem), `candidate` (ArticleCandidate)
  - Output: Returns `tuple[NewsArticle, bool]`.
  - Why: `IncidentIntelligenceRepository.upsert_article` provides the src/ghostrecon/services/incident_intelligence.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `NewsArticle`, `add`, `self._enqueue_event`, `scalar`, `flush`, `new_event`, `where`, `select`; uses database session queries, database writes, idempotency lookup, outbox/event emission.
  - Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async upsert_incident(source: SourceDefinition, raw_item: RawSourceItem, article: NewsArticle, candidate: IncidentCandidate) -> tuple[SecurityIncident, bool, bool]`
  - Inputs: `source` (SourceDefinition), `raw_item` (RawSourceItem), `article` (NewsArticle), `candidate` (IncidentCandidate)
  - Output: Returns `tuple[SecurityIncident, bool, bool]`.
  - Why: `IncidentIntelligenceRepository.upsert_incident` provides the src/ghostrecon/services/incident_intelligence.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `self._apply_corroboration`, `scalar`, `SecurityIncident`, `add`, `self._enqueue_event`, `_append_unique`, `_merge_list`, `self._link_evidence`; uses database session queries, database writes, idempotency lookup, outbox/event emission.
  - Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async list_incidents(*, status: str | None, source: str | None, company: str | None, limit: int) -> list[SecurityIncident]`
  - Inputs: `status` (str | None), `source` (str | None), `company` (str | None), `limit` (int)
  - Output: Returns `list[SecurityIncident]`.
  - Why: `IncidentIntelligenceRepository.list_incidents` retrieves a bounded collection for API or workflow callers.
  - How: It calls `limit`, `stmt.where`, `execute`, `result.scalars`, `_slug`, `order_by`, `desc`, `any`; uses database session queries, parsing/normalization.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async list_watch_targets(*, target_type: str | None, enabled: bool | None, limit: int) -> list[WatchTarget]`
  - Inputs: `target_type` (str | None), `enabled` (bool | None), `limit` (int)
  - Output: Returns `list[WatchTarget]`.
  - Why: `IncidentIntelligenceRepository.list_watch_targets` retrieves a bounded collection for API or workflow callers.
  - How: It calls `limit`, `stmt.where`, `execute`, `result.scalars`, `order_by`, `desc`, `select`; uses database session queries.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async create_watch_target(payload: WatchTargetCreate, actor: str, idempotency_key: str) -> WatchTarget`
  - Inputs: `payload` (WatchTargetCreate), `actor` (str), `idempotency_key` (str)
  - Output: Returns `WatchTarget`.
  - Why: `IncidentIntelligenceRepository.create_watch_target` creates and persists a new domain object while enforcing idempotency and policy.
  - How: It calls `_watch_target_key`, `WatchTarget`, `add`, `self._audit`, `self._enqueue_event`, `scalar`, `flush`, `new_event`; uses database session queries, database writes, idempotency lookup, outbox/event emission.
  - Side effects: mutates database state; adds outbox/event records; runs asynchronously and may await database or provider operations.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `async patch_watch_target(watch_target_id: str, payload: WatchTargetPatch, actor: str, idempotency_key: str) -> WatchTarget | None`
  - Inputs: `watch_target_id` (str), `payload` (WatchTargetPatch), `actor` (str), `idempotency_key` (str)
  - Output: Returns `WatchTarget | None`; callers must handle the documented not-found or unavailable path.
  - Why: `IncidentIntelligenceRepository.patch_watch_target` applies a partial update while preserving validation and audit behavior.
  - How: It calls `self._audit`, `get`, `ValueError`; uses database session queries, idempotency lookup.
  - Side effects: runs asynchronously and may await database or provider operations.
  - Failures: raises `ValueError`; may return `None` for not-found or unavailable data.
- `async _link_evidence(incident: SecurityIncident, article: NewsArticle, raw_item: RawSourceItem, candidate: IncidentCandidate) -> None`
  - Inputs: `incident` (SecurityIncident), `article` (NewsArticle), `raw_item` (RawSourceItem), `candidate` (IncidentCandidate)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: `IncidentIntelligenceRepository._link_evidence` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `add`, `scalar`, `SecurityIncidentEvidence`, `where`, `select`; uses database session queries, database writes.
  - Side effects: mutates database state; runs asynchronously and may await database or provider operations.
  - Failures: may return `None` for not-found or unavailable data.
- `_apply_corroboration(incident: SecurityIncident, candidate: IncidentCandidate) -> None`
  - Inputs: `incident` (SecurityIncident), `candidate` (IncidentCandidate)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: `IncidentIntelligenceRepository._apply_corroboration` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.
- `_audit(actor: str, action: str, entity_type: str, entity_id: str, idempotency_key: str) -> None`
  - Inputs: `actor` (str), `action` (str), `entity_type` (str), `entity_id` (str), `idempotency_key` (str)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: `IncidentIntelligenceRepository._audit` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
  - How: It calls `add`, `AuditEvent`; uses database writes, idempotency lookup.
  - Side effects: mutates database state.
  - Failures: may return `None` for not-found or unavailable data.
- `_enqueue_event(event: Any) -> OutboxEvent`
  - Inputs: `event` (Any)
  - Output: Returns `OutboxEvent`.
  - Why: `IncidentIntelligenceRepository._enqueue_event` creates an outbox event record for asynchronous consumers.
  - How: It calls `event.model_dump`, `OutboxEvent`, `add`; uses database writes, idempotency lookup, outbox/event emission, serialization/projection.
  - Side effects: mutates database state; adds outbox/event records.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

#### Module Functions

##### `article_candidate_from_raw_item(source: SourceDefinition, raw_item: RawSourceItem) -> ArticleCandidate`

- Inputs: `source` (SourceDefinition), `raw_item` (RawSourceItem)
- Output: Returns `ArticleCandidate`.
- Why: `article_candidate_from_raw_item` provides the src/ghostrecon/services/incident_intelligence.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_slug`, `hexdigest`, `ArticleCandidate`, `isinstance`, `metadata.get`, `_string`, `_hostname`, `isoformat`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `incident_candidate_from_article(source: SourceDefinition, raw_item: RawSourceItem, article: ArticleCandidate) -> IncidentCandidate | None`

- Inputs: `source` (SourceDefinition), `raw_item` (RawSourceItem), `article` (ArticleCandidate)
- Output: Returns `IncidentCandidate | None`; callers must handle the documented not-found or unavailable path.
- Why: `incident_candidate_from_article` provides the src/ghostrecon/services/incident_intelligence.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `join`, `text.lower`, `_domains_from_metadata`, `_attack_vector`, `bool`, `hexdigest`, `IncidentCandidate`, `isinstance`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `async fetch_incident_source(source_definition_id: str, settings: Settings | None = None) -> dict[str, object]`

- Inputs: `source_definition_id` (str), `settings` (Settings | None)
- Output: Returns `dict[str, object]`.
- Why: `fetch_incident_source` retrieves external or registered source data.
- How: It calls `fetch_source_by_id`, `parse_pending_incident_items`; uses parsing/normalization.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async parse_pending_incident_items(source_definition_id: str | None = None, settings: Settings | None = None) -> dict[str, object]`

- Inputs: `source_definition_id` (str | None), `settings` (Settings | None)
- Output: Returns `dict[str, object]`.
- Why: `parse_pending_incident_items` converts raw external content into normalized internal objects.
- How: It calls `session_scope`, `IncidentIntelligenceRepository`, `repository.parse_pending_items`; uses parsing/normalization.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async list_incidents(*, status: str | None = None, source: str | None = None, company: str | None = None, limit: int = 100, settings: Settings | None = None) -> list[SecurityIncident]`

- Inputs: `status` (str | None), `source` (str | None), `company` (str | None), `limit` (int), `settings` (Settings | None)
- Output: Returns `list[SecurityIncident]`.
- Why: `list_incidents` retrieves a bounded collection for API or workflow callers.
- How: It calls `session_scope`, `IncidentIntelligenceRepository`, `repository.list_incidents`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_incident(incident_id: str, settings: Settings | None = None) -> SecurityIncident | None`

- Inputs: `incident_id` (str), `settings` (Settings | None)
- Output: Returns `SecurityIncident | None`; callers must handle the documented not-found or unavailable path.
- Why: `get_incident` loads one record or detail object for API or workflow callers.
- How: It calls `session_scope`, `session.get`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async list_watch_targets(*, target_type: str | None = None, enabled: bool | None = None, limit: int = 100, settings: Settings | None = None) -> list[WatchTarget]`

- Inputs: `target_type` (str | None), `enabled` (bool | None), `limit` (int), `settings` (Settings | None)
- Output: Returns `list[WatchTarget]`.
- Why: `list_watch_targets` retrieves a bounded collection for API or workflow callers.
- How: It calls `session_scope`, `IncidentIntelligenceRepository`, `repository.list_watch_targets`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async create_watch_target(payload: WatchTargetCreate, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> WatchTarget`

- Inputs: `payload` (WatchTargetCreate), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `WatchTarget`.
- Why: `create_watch_target` creates and persists a new domain object while enforcing idempotency and policy.
- How: It calls `session_scope`, `IncidentIntelligenceRepository`, `repository.create_watch_target`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async patch_watch_target(watch_target_id: str, payload: WatchTargetPatch, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> WatchTarget | None`

- Inputs: `watch_target_id` (str), `payload` (WatchTargetPatch), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `WatchTarget | None`; callers must handle the documented not-found or unavailable path.
- Why: `patch_watch_target` applies a partial update while preserving validation and audit behavior.
- How: It calls `session_scope`, `IncidentIntelligenceRepository`, `repository.patch_watch_target`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async create_manual_incident(request: ManualIncidentCreate, *, actor: str, idempotency_key: str, settings: Settings | None = None) -> list[SecurityIncident]`

- Inputs: `request` (ManualIncidentCreate), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `list[SecurityIncident]`.
- Why: `create_manual_incident` records operator-supplied incident evidence as canonical company/domain-scoped incident rows.
- How: It derives one context per company/domain pair, shares an `incident_group_key`, writes incidents idempotently, and emits audit/outbox events.
- Side effects: mutates database state; adds audit/outbox records.
- Failures: upstream callers still need to handle dependency errors from invoked helpers.

##### `async promote_incident_to_watchlist(incident_id: str, *, version: int, actor: str, idempotency_key: str, settings: Settings | None = None) -> WatchTarget | None`

- Inputs: `incident_id` (str), `version` (int), `actor` (str), `idempotency_key` (str), `settings` (Settings | None)
- Output: Returns `WatchTarget | None`; callers must handle the documented not-found or unavailable path.
- Why: `promote_incident_to_watchlist` turns an upstream intelligence object into a downstream workflow target.
- How: It checks incident version/status/company context, builds a `company` watch target owned by the actor, and delegates idempotent target creation to the repository.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `ValueError` for version conflicts or invalid state; may return `None` for not-found or unavailable data.

##### `incident_to_api(incident: SecurityIncident) -> dict[str, object]`

- Inputs: `incident` (SecurityIncident)
- Output: Returns `dict[str, object]`.
- Why: `incident_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `watch_target_to_api(target: WatchTarget) -> dict[str, object]`

- Inputs: `target` (WatchTarget)
- Output: Returns `dict[str, object]`.
- Why: `watch_target_to_api` serializes a persisted ORM object into the API/model contract.
- How: It uses serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_append_unique(values: list[object] | None, value: object) -> list[object]`

- Inputs: `values` (list[object] | None), `value` (object)
- Output: Returns `list[object]`.
- Why: `_append_unique` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `resolved.append`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_merge_list(left: list[object] | None, right: list[object] | None) -> list[object]`

- Inputs: `left` (list[object] | None), `right` (list[object] | None)
- Output: Returns `list[object]`.
- Why: `_merge_list` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `merged.append`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_companies_from_metadata(metadata: dict[str, object]) -> list[object]`

- Inputs: `metadata` (dict[str, object])
- Output: Returns `list[object]`.
- Why: `_companies_from_metadata` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `metadata.get`, `isinstance`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_companies_from_text(text: str) -> list[object]`

- Inputs: `text` (str)
- Output: Returns `list[object]`.
- Why: `_companies_from_text` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `re.search`, `match.group`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_domains_from_metadata(metadata: dict[str, object]) -> list[object]`

- Inputs: `metadata` (dict[str, object])
- Output: Returns `list[object]`.
- Why: `_domains_from_metadata` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `metadata.get`, `isinstance`, `lower`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_attack_vector(lowered: str) -> str | None`

- Inputs: `lowered` (str)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_attack_vector` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_ATTACK_VECTORS.items`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_watch_target_key(target_type: str, key: str) -> str`

- Inputs: `target_type` (str), `key` (str)
- Output: Returns `str`.
- Why: `_watch_target_key` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `lower`, `_slug`, `key.strip`, `_hostname`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_hostname(url: str | None) -> str | None`

- Inputs: `url` (str | None)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_hostname` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `lower`, `urlsplit`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_string(value: object) -> str | None`

- Inputs: `value` (object)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `_string` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `_slug(value: str) -> str`

- Inputs: `value` (str)
- Output: Returns `str`.
- Why: `_slug` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `re.sub`, `value.lower`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

### `src/ghostrecon/services/security_feeds.py`

#### Module Functions

##### `async fetch_cisa_kev() -> list[dict[str, Any]]`

- Inputs: No external inputs.
- Output: Returns `list[dict[str, Any]]`.
- Why: `fetch_cisa_kev` retrieves external or registered source data.
- How: It calls `httpx.AsyncClient`, `response.raise_for_status`, `response.json`, `payload.get`, `client.get`; uses HTTP/provider IO.
- Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async fetch_nvd_cves_for_keyword(keyword: str, max_results: int = 20) -> list[dict[str, Any]]`

- Inputs: `keyword` (str), `max_results` (int)
- Output: Returns `list[dict[str, Any]]`.
- Why: `fetch_nvd_cves_for_keyword` retrieves external or registered source data.
- How: It calls `min`, `httpx.AsyncClient`, `response.raise_for_status`, `response.json`, `payload.get`, `client.get`; uses HTTP/provider IO.
- Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `map_security_signal(raw: dict[str, Any], source: str) -> dict[str, object]`

- Inputs: `raw` (dict[str, Any]), `source` (str)
- Output: Returns `dict[str, object]`.
- Why: `map_security_signal` projects provider-specific data into GhostRecon shape.
- How: It calls `get`, `isoformat`, `raw.get`, `datetime.now`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

## Shared Module Notes

- `src/ghostrecon/services/source_registry.py` is shared or mounted behavior used by this service; its exhaustive function reference lives in the service that owns that module in the mapping, or in `gateway-service` for route/factory code.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_incident_intelligence.py`
- `tests/unit/test_incident_routes.py`
