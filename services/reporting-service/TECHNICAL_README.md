
# reporting-service Technical README

## Architecture

Reporting Service is implemented by `src/ghostrecon/services/reporting/`. It is exposed through `reporting_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | `GET` | `/v1/intelligence/sources/health` | `source_health` |
| service | `GET` | `/v1/reporting/events` | `reporting_events` |
| service | `GET` | `/v1/reporting/events/{event_id}` | `reporting_event_detail` |
| service | `GET` | `/v1/reporting/incidents` | `reporting_incidents` |
| service | `GET` | `/v1/reporting/incidents/{incident_id}` | `reporting_incident_detail` |
| service | `GET` | `/v1/reporting/watch-targets` | `reporting_watch_targets` |
| service | `GET` | `/v1/reporting/review-queue` | `reporting_review_queue` |
| service | `GET` | `/v1/reporting/crm-targets` | `reporting_crm_targets` |
| service | `GET` | `/v1/reporting/meetings` | `reporting_meetings` |
| service | `GET` | `/v1/reporting/meetings/{meeting_id}` | `reporting_meeting_detail` |
| service | `GET` | `/v1/reporting/source-health` | `reporting_source_health` |
| service | `GET` | `/v1/reporting/kpis/catalog` | `reporting_kpi_catalog` |
| service | `GET` | `/v1/kpis/catalog` | `kpi_catalog` |
| gateway | `GET` | `/v1/intelligence/sources/health` | `source_health` |
| gateway | `GET` | `/v1/reporting/events` | `reporting_events` |
| gateway | `GET` | `/v1/reporting/events/{event_id}` | `reporting_event_detail` |
| gateway | `GET` | `/v1/reporting/incidents` | `reporting_incidents` |
| gateway | `GET` | `/v1/reporting/incidents/{incident_id}` | `reporting_incident_detail` |
| gateway | `GET` | `/v1/reporting/watch-targets` | `reporting_watch_targets` |
| gateway | `GET` | `/v1/reporting/review-queue` | `reporting_review_queue` |
| gateway | `GET` | `/v1/reporting/crm-targets` | `reporting_crm_targets` |
| gateway | `GET` | `/v1/reporting/meetings` | `reporting_meetings` |
| gateway | `GET` | `/v1/reporting/meetings/{meeting_id}` | `reporting_meeting_detail` |
| gateway | `GET` | `/v1/reporting/source-health` | `reporting_source_health` |
| gateway | `GET` | `/v1/reporting/kpis/catalog` | `reporting_kpi_catalog` |
| gateway | `GET` | `/v1/kpis/catalog` | `kpi_catalog` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.
- Event projections include exact address and geocode fields; incident projections include company/domain context and evidence URLs for dashboard inline rendering.
- Event format filters accept canonical values and legacy `physical`/`virtual` aliases.

## Function Reference

### `src/ghostrecon/services/reporting/`

#### Module Functions

##### `reporting_metadata_from_sources(sources: list[SourceHealth], *, generated_at: datetime | None = None, record_watermark_name: str | None = None, record_watermark: datetime | None = None) -> ReportingMetadata`

- Inputs: `sources` (list[SourceHealth]), `generated_at` (datetime | None), `record_watermark_name` (str | None), `record_watermark` (datetime | None)
- Output: Returns `ReportingMetadata`.
- Why: `reporting_metadata_from_sources` provides the src/ghostrecon/services/reporting/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_latest_datetime`, `ReportingMetadata`, `datetime.now`, `bool`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async reporting_metadata(kind: str | None = None, *, settings: Settings | None = None, record_watermark_name: str | None = None, record_watermark: datetime | None = None) -> ReportingMetadata`

- Inputs: `kind` (str | None), `settings` (Settings | None), `record_watermark_name` (str | None), `record_watermark` (datetime | None)
- Output: Returns `ReportingMetadata`.
- Why: `reporting_metadata` provides the src/ghostrecon/services/reporting/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `reporting_metadata_from_sources`; uses time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_reporting_events(*, series: str | None = None, source: str | None = None, country: str | None = None, event_format: str | None = None, topic: str | None = None, cursor: str | None = None, limit: int = 100, operator: ReportingOperatorContext | None = None, settings: Settings | None = None) -> ReportingEventList`

- Inputs: `series` (str | None), `source` (str | None), `country` (str | None), `event_format` (str | None), `topic` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext | None), `settings` (Settings | None)
- Output: Returns `ReportingEventList`.
- Why: `get_reporting_events` loads one record or detail object for API or workflow callers.
- How: It calls `parse_cursor`, `ReportingEventList`, `session_scope`, `order_by`, `reporting_metadata`, `nullslast`, `asc`, `stmt.where`; uses database session queries, parsing/normalization, serialization/projection, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_reporting_event_detail(event_id: str, *, operator: ReportingOperatorContext | None = None, settings: Settings | None = None) -> ReportingEventDetail | None`

- Inputs: `event_id` (str), `operator` (ReportingOperatorContext | None), `settings` (Settings | None)
- Output: Returns `ReportingEventDetail | None`; callers must handle the documented not-found or unavailable path.
- Why: `get_reporting_event_detail` loads one record or detail object for API or workflow callers.
- How: It calls `ReportingEventDetail`, `session_scope`, `reporting_metadata`, `session.get`, `CyberEventOut.model_validate`, `event_to_api`; uses database session queries, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async get_reporting_incidents(*, status: str | None = None, source: str | None = None, company: str | None = None, attack_vector: str | None = None, incident_type: str | None = None, cursor: str | None = None, limit: int = 100, operator: ReportingOperatorContext | None = None, settings: Settings | None = None) -> ReportingIncidentList`

- Inputs: `status` (str | None), `source` (str | None), `company` (str | None), `attack_vector` (str | None), `incident_type` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext | None), `settings` (Settings | None)
- Output: Returns `ReportingIncidentList`.
- Why: `get_reporting_incidents` loads one record or detail object for API or workflow callers.
- How: It calls `parse_cursor`, `ReportingIncidentList`, `session_scope`, `order_by`, `reporting_metadata`, `desc`, `asc`, `stmt.where`; uses database session queries, parsing/normalization, serialization/projection, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_reporting_incident_detail(incident_id: str, *, operator: ReportingOperatorContext | None = None, settings: Settings | None = None) -> ReportingIncidentDetail | None`

- Inputs: `incident_id` (str), `operator` (ReportingOperatorContext | None), `settings` (Settings | None)
- Output: Returns `ReportingIncidentDetail | None`; callers must handle the documented not-found or unavailable path.
- Why: `get_reporting_incident_detail` loads one record or detail object for API or workflow callers.
- How: It calls `ReportingIncidentDetail`, `session_scope`, `reporting_metadata`, `session.get`, `SecurityIncidentOut.model_validate`, `incident_to_api`; uses database session queries, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async get_reporting_watch_targets(*, target_type: str | None = None, enabled: bool | None = None, owner: str | None = None, cursor: str | None = None, limit: int = 100, operator: ReportingOperatorContext | None = None, settings: Settings | None = None) -> ReportingWatchTargetList`

- Inputs: `target_type` (str | None), `enabled` (bool | None), `owner` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext | None), `settings` (Settings | None)
- Output: Returns `ReportingWatchTargetList`.
- Why: `get_reporting_watch_targets` loads one record or detail object for API or workflow callers.
- How: It calls `parse_cursor`, `ReportingWatchTargetList`, `session_scope`, `order_by`, `reporting_metadata`, `desc`, `asc`, `stmt.where`; uses database session queries, parsing/normalization, serialization/projection, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_reporting_review_queue(*, status: str | None = 'open', candidate_type: str | None = None, target_type: str | None = None, cursor: str | None = None, limit: int = 100, operator: ReportingOperatorContext | None = None, settings: Settings | None = None) -> ReportingReviewQueue`

- Inputs: `status` (str | None), `candidate_type` (str | None), `target_type` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext | None), `settings` (Settings | None)
- Output: Returns `ReportingReviewQueue`.
- Why: `get_reporting_review_queue` loads one record or detail object for API or workflow callers.
- How: It calls `parse_cursor`, `ReportingReviewQueue`, `ReportingOperatorContext`, `session_scope`, `order_by`, `reporting_metadata`, `asc`, `stmt.where`; uses database session queries, parsing/normalization, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_reporting_crm_targets(*, status: str | None = None, target_type: str | None = None, export_status: str | None = None, cursor: str | None = None, limit: int = 100, operator: ReportingOperatorContext | None = None, settings: Settings | None = None) -> ReportingCrmTargetList`

- Inputs: `status` (str | None), `target_type` (str | None), `export_status` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext | None), `settings` (Settings | None)
- Output: Returns `ReportingCrmTargetList`.
- Why: `get_reporting_crm_targets` loads one record or detail object for API or workflow callers.
- How: It calls `parse_cursor`, `ReportingCrmTargetList`, `ReportingOperatorContext`, `session_scope`, `order_by`, `reporting_metadata`, `desc`, `asc`; uses database session queries, parsing/normalization, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_reporting_source_health(*, kind: str | None = None, freshness_status: str | None = None, cursor: str | None = None, limit: int = 100, operator: ReportingOperatorContext | None = None, settings: Settings | None = None) -> ReportingSourceHealthList`

- Inputs: `kind` (str | None), `freshness_status` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext | None), `settings` (Settings | None)
- Output: Returns `ReportingSourceHealthList`.
- Why: `get_reporting_source_health` loads one record or detail object for API or workflow callers.
- How: It calls `parse_cursor`, `reporting_metadata_from_sources`, `ReportingSourceHealthList`, `ReportingOperatorContext`, `_latest_datetime`, `next_cursor`, `project_source_health`; uses parsing/normalization, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_reporting_meetings(*, status: str | None = None, crm_sync_status: str | None = None, cursor: str | None = None, limit: int = 100, operator: ReportingOperatorContext | None = None, settings: Settings | None = None) -> ReportingMeetingList`

- Inputs: `status` (str | None), `crm_sync_status` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext | None), `settings` (Settings | None)
- Output: Returns `ReportingMeetingList`.
- Why: `get_reporting_meetings` loads one record or detail object for API or workflow callers.
- How: It calls `parse_cursor`, `ReportingMeetingList`, `ReportingOperatorContext`, `session_scope`, `order_by`, `reporting_metadata`, `desc`, `asc`; uses database session queries, parsing/normalization, time calculations.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async get_reporting_meeting_detail(meeting_id: str, *, operator: ReportingOperatorContext | None = None, settings: Settings | None = None) -> ReportingMeetingDetail | None`

- Inputs: `meeting_id` (str), `operator` (ReportingOperatorContext | None), `settings` (Settings | None)
- Output: Returns `ReportingMeetingDetail | None`; callers must handle the documented not-found or unavailable path.
- Why: `get_reporting_meeting_detail` loads one record or detail object for API or workflow callers.
- How: It calls `ReportingMeetingDetail`, `ReportingOperatorContext`, `session_scope`, `reporting_metadata`, `session.get`, `_project_meeting_with_children`; uses database session queries.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: may return `None` for not-found or unavailable data.

##### `async get_reporting_kpi_catalog(*, operator: ReportingOperatorContext | None = None, settings: Settings | None = None) -> ReportingKpiCatalog`

- Inputs: `operator` (ReportingOperatorContext | None), `settings` (Settings | None)
- Output: Returns `ReportingKpiCatalog`.
- Why: `get_reporting_kpi_catalog` loads one record or detail object for API or workflow callers.
- How: It calls `ReportingKpiCatalog`, `reporting_metadata`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `parse_cursor(cursor: str | None) -> int`

- Inputs: `cursor` (str | None)
- Output: Returns `int`.
- Why: `parse_cursor` converts raw external content into normalized internal objects.
- How: It calls `ValueError`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `ValueError`; catches provider or validation errors and maps them to the module contract.

##### `next_cursor(rows: list[Any], limit: int, offset: int) -> str | None`

- Inputs: `rows` (list[Any]), `limit` (int), `offset` (int)
- Output: Returns `str | None`; callers must handle the documented not-found or unavailable path.
- Why: `next_cursor` provides the src/ghostrecon/services/reporting/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

##### `project_review_candidate(candidate: ReviewCandidate, context: ReportingOperatorContext) -> ReviewCandidateOut`

- Inputs: `candidate` (ReviewCandidate), `context` (ReportingOperatorContext)
- Output: Returns `ReviewCandidateOut`.
- Why: `project_review_candidate` creates reporting-facing dictionaries from persisted records.
- How: It calls `review_candidate_to_api`, `ReviewCandidateOut.model_validate`; uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `project_crm_target(target: CrmTarget, context: ReportingOperatorContext) -> CrmTargetOut`

- Inputs: `target` (CrmTarget), `context` (ReportingOperatorContext)
- Output: Returns `CrmTargetOut`.
- Why: `project_crm_target` creates reporting-facing dictionaries from persisted records.
- How: It calls `crm_target_to_api`, `CrmTargetOut.model_validate`; uses policy validation, serialization/projection.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `project_source_health(source: SourceHealth, context: ReportingOperatorContext) -> SourceHealth`

- Inputs: `source` (SourceHealth), `context` (ReportingOperatorContext)
- Output: Returns `SourceHealth`.
- Why: `project_source_health` creates reporting-facing dictionaries from persisted records.
- How: It calls `source.model_copy`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async _project_meeting_with_children(session: Any, meeting: MeetingHandoff, context: ReportingOperatorContext) -> MeetingHandoffOut`

- Inputs: `session` (Any), `meeting` (MeetingHandoff), `context` (ReportingOperatorContext)
- Output: Returns `MeetingHandoffOut`.
- Why: `_project_meeting_with_children` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `meeting_to_model`, `session.scalar`, `scalars`, `model.model_copy`, `limit`, `order_by`, `session.execute`, `desc`; uses database session queries, policy validation, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_latest_datetime(values: Any) -> datetime | None`

- Inputs: `values` (Any)
- Output: Returns `datetime | None`; callers must handle the documented not-found or unavailable path.
- Why: `_latest_datetime` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `max`, `isinstance`; uses time calculations.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_reporting_routes.py`

## Startup and dependency contract

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns database only. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Database-owning APIs verify the migrated schema; configured provider checks are named without exposing credentials.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
