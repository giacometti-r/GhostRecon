
# gateway-service Technical README

## Architecture

Gateway Service is implemented by `src/ghostrecon/service_apps/routers.py`, `src/ghostrecon/service_apps/factory.py`, `src/ghostrecon/service_apps/entrypoint.py`, `src/ghostrecon/service_apps/runtime.py`. It is exposed through `gateway_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| gateway | `GET` | `/v1/service-map` | `service_map` |
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
| gateway | `GET` | `/v1/intelligence/events` | `intelligence_events` |
| gateway | `POST` | `/v1/intelligence/events/manual` | `intelligence_create_manual_event` |
| gateway | `PATCH` | `/v1/intelligence/events/{event_id}` | `intelligence_patch_event` |
| gateway | `GET` | `/v1/intelligence/events/{event_id}` | `intelligence_event_detail` |
| gateway | `GET` | `/v1/intelligence/events/{event_id}/participants` | `intelligence_event_participants` |
| gateway | `GET` | `/v1/intelligence/participants` | `intelligence_participants` |
| gateway | `GET` | `/v1/intelligence/incidents` | `intelligence_incidents` |
| gateway | `POST` | `/v1/intelligence/incidents/manual` | `intelligence_create_manual_incident` |
| gateway | `GET` | `/v1/intelligence/incidents/{incident_id}` | `intelligence_incident_detail` |
| gateway | `GET` | `/v1/intelligence/watch-targets` | `intelligence_watch_targets` |
| gateway | `POST` | `/v1/intelligence/watch-targets` | `intelligence_create_watch_target` |
| gateway | `PATCH` | `/v1/intelligence/watch-targets/{watch_target_id}` | `intelligence_patch_watch_target` |
| gateway | `POST` | `/v1/intelligence/incidents/{incident_id}/promote-to-watchlist` | `intelligence_promote_incident_to_watchlist` |
| gateway | `POST` | `/v1/crm/exports` | `crm_export_start` |
| gateway | `GET` | `/v1/crm/exports/{batch_id}` | `crm_export_detail` |
| gateway | `POST` | `/v1/crm/exports/{batch_id}/retry-failed` | `crm_export_retry_failed` |
| gateway | `POST` | `/v1/enrichment/entity-resolutions` | `enrichment_create_entity_resolution` |
| gateway | `GET` | `/v1/enrichment/entity-resolutions` | `enrichment_entity_resolutions` |
| gateway | `POST` | `/v1/enrichment/contact-candidates` | `enrichment_create_contact_candidate` |
| gateway | `GET` | `/v1/enrichment/contact-candidates` | `enrichment_contact_candidates` |
| gateway | `POST` | `/v1/enrichment/event-participants/{participant_id}/enrich-target` | `enrichment_event_participant_enrich_target` |
| gateway | `POST` | `/v1/email/candidates/persist` | `email_persist_candidates` |
| gateway | `POST` | `/v1/email/verify-batch` | `email_verify_batch` |
| gateway | `POST` | `/v1/scoring/candidates` | `candidate_score` |
| gateway | `POST` | `/v1/sequences/evaluate` | `sequence_eligibility` |
| gateway | `POST` | `/v1/sequences` | `sequence_create` |
| gateway | `POST` | `/v1/sequences/enrollments` | `sequence_enrollment_create` |
| gateway | `GET` | `/v1/sequences/enrollments` | `sequence_enrollment_list` |
| gateway | `GET` | `/v1/sequences/enrollments/{enrollment_id}` | `sequence_enrollment_detail` |
| gateway | `POST` | `/v1/sequences/enrollments/{enrollment_id}/pause` | `sequence_enrollment_pause` |
| gateway | `POST` | `/v1/sequences/enrollments/{enrollment_id}/resume` | `sequence_enrollment_resume` |
| gateway | `POST` | `/v1/sequences/enrollments/{enrollment_id}/cancel` | `sequence_enrollment_cancel` |
| gateway | `POST` | `/v1/sequences/unsubscribe` | `sequence_unsubscribe` |
| gateway | `POST` | `/v1/calendar/availability` | `calendar_availability` |
| gateway | `POST` | `/v1/meetings` | `meeting_create` |
| gateway | `GET` | `/v1/meetings` | `meeting_list` |
| gateway | `GET` | `/v1/meetings/{meeting_id}` | `meeting_detail` |
| gateway | `POST` | `/v1/meetings/{meeting_id}/prep-packet` | `meeting_generate_prep_packet` |
| gateway | `POST` | `/v1/meetings/{meeting_id}/outcome` | `meeting_record_outcome` |
| gateway | `POST` | `/v1/meetings/{meeting_id}/cancel` | `meeting_cancel` |
| gateway | `POST` | `/v1/meetings/{meeting_id}/retry-sync` | `meeting_retry_sync` |
| gateway | `POST` | `/v1/meetings/prep-packet` | `prep_packet` |
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
| gateway | `GET` | `/v1/kpis/catalog` | `kpi_catalog` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.
- Sprint 17/18 workflow routes add manual event create/edit, manual incident splitting, version-aware incident promotion/revert, and durable event participant enrichment queueing.

## Function Reference

### `src/ghostrecon/service_apps/routers.py`

#### Module Functions

##### `reporting_operator_context(actor: str = Header(default='system', alias='X-Actor'), operator_role: str = Header(default=DashboardRole.VIEWER.value, alias='X-Operator-Role')) -> ReportingOperatorContext`

- Inputs: `actor` (str), `operator_role` (str)
- Output: Returns `ReportingOperatorContext`.
- Why: `reporting_operator_context` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `ReportingOperatorContext`, `DashboardRole`, `HTTPException`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async service_map() -> dict[str, list[str]]`

- Inputs: No external inputs.
- Output: Returns `dict[str, list[str]]`.
- Why: `service_map` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `ROUTERS.keys`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async source_health(kind: str | None = None) -> SourceHealthList`

- Inputs: `kind` (str | None)
- Output: Returns `SourceHealthList`.
- Why: `source_health` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `SourceHealthList`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async reporting_events(series: str | None = None, source: str | None = None, country: str | None = None, event_format: str | None = None, topic: str | None = None, cursor: str | None = None, limit: int = Query(default=100, ge=1, le=500), operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingEventList`

- Inputs: `series` (str | None), `source` (str | None), `country` (str | None), `event_format` (str | None), `topic` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext)
- Output: Returns `ReportingEventList`.
- Why: `reporting_events` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `get_reporting_events`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async reporting_event_detail(event_id: str, operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingEventDetail`

- Inputs: `event_id` (str), `operator` (ReportingOperatorContext)
- Output: Returns `ReportingEventDetail`.
- Why: `reporting_event_detail` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_reporting_event_detail`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async reporting_incidents(status: str | None = None, source: str | None = None, company: str | None = None, attack_vector: str | None = None, incident_type: str | None = None, cursor: str | None = None, limit: int = Query(default=100, ge=1, le=500), operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingIncidentList`

- Inputs: `status` (str | None), `source` (str | None), `company` (str | None), `attack_vector` (str | None), `incident_type` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext)
- Output: Returns `ReportingIncidentList`.
- Why: `reporting_incidents` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `get_reporting_incidents`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async reporting_incident_detail(incident_id: str, operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingIncidentDetail`

- Inputs: `incident_id` (str), `operator` (ReportingOperatorContext)
- Output: Returns `ReportingIncidentDetail`.
- Why: `reporting_incident_detail` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_reporting_incident_detail`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async reporting_watch_targets(target_type: str | None = None, enabled: bool | None = None, owner: str | None = None, cursor: str | None = None, limit: int = Query(default=100, ge=1, le=500), operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingWatchTargetList`

- Inputs: `target_type` (str | None), `enabled` (bool | None), `owner` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext)
- Output: Returns `ReportingWatchTargetList`.
- Why: `reporting_watch_targets` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `get_reporting_watch_targets`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async reporting_review_queue(status: str | None = 'open', candidate_type: str | None = None, target_type: str | None = None, cursor: str | None = None, limit: int = Query(default=100, ge=1, le=500), operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingReviewQueue`

- Inputs: `status` (str | None), `candidate_type` (str | None), `target_type` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext)
- Output: Returns `ReportingReviewQueue`.
- Why: `reporting_review_queue` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `get_reporting_review_queue`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async reporting_crm_targets(status: str | None = None, target_type: str | None = None, export_status: str | None = None, cursor: str | None = None, limit: int = Query(default=100, ge=1, le=500), operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingCrmTargetList`

- Inputs: `status` (str | None), `target_type` (str | None), `export_status` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext)
- Output: Returns `ReportingCrmTargetList`.
- Why: `reporting_crm_targets` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `get_reporting_crm_targets`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async reporting_meetings(status: str | None = None, crm_sync_status: str | None = None, cursor: str | None = None, limit: int = Query(default=100, ge=1, le=500), operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingMeetingList`

- Inputs: `status` (str | None), `crm_sync_status` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext)
- Output: Returns `ReportingMeetingList`.
- Why: `reporting_meetings` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `get_reporting_meetings`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async reporting_meeting_detail(meeting_id: str, operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingMeetingDetail`

- Inputs: `meeting_id` (str), `operator` (ReportingOperatorContext)
- Output: Returns `ReportingMeetingDetail`.
- Why: `reporting_meeting_detail` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_reporting_meeting_detail`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async reporting_source_health(kind: str | None = None, freshness_status: str | None = None, cursor: str | None = None, limit: int = Query(default=100, ge=1, le=500), operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingSourceHealthList`

- Inputs: `kind` (str | None), `freshness_status` (str | None), `cursor` (str | None), `limit` (int), `operator` (ReportingOperatorContext)
- Output: Returns `ReportingSourceHealthList`.
- Why: `reporting_source_health` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `get_reporting_source_health`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async reporting_kpi_catalog(operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingKpiCatalog`

- Inputs: `operator` (ReportingOperatorContext)
- Output: Returns `ReportingKpiCatalog`.
- Why: `reporting_kpi_catalog` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_reporting_kpi_catalog`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async intelligence_events(series: str | None = None, source: str | None = None, country: str | None = None, event_format: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> CyberEventList`

- Inputs: `series` (str | None), `source` (str | None), `country` (str | None), `event_format` (str | None), `limit` (int)
- Output: Returns `CyberEventList`.
- Why: `intelligence_events` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `CyberEventList`, `get_settings`, `CyberEventOut.model_validate`, `event_to_api`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async intelligence_event_detail(event_id: str) -> CyberEventOut`

- Inputs: `event_id` (str)
- Output: Returns `CyberEventOut`.
- Why: `intelligence_event_detail` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `CyberEventOut.model_validate`, `get_event`, `HTTPException`, `event_to_api`, `get_settings`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async intelligence_event_participants(event_id: str, reuse_state: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> EventParticipantList`

- Inputs: `event_id` (str), `reuse_state` (str | None), `limit` (int)
- Output: Returns `EventParticipantList`.
- Why: `intelligence_event_participants` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `EventParticipantList`, `get_event`, `HTTPException`, `get_settings`, `EventParticipantOut.model_validate`, `participant_to_api`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async intelligence_participants(event_id: str | None = None, reuse_state: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> EventParticipantList`

- Inputs: `event_id` (str | None), `reuse_state` (str | None), `limit` (int)
- Output: Returns `EventParticipantList`.
- Why: `intelligence_participants` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `EventParticipantList`, `get_settings`, `EventParticipantOut.model_validate`, `participant_to_api`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async intelligence_incidents(status: str | None = None, source: str | None = None, company: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> SecurityIncidentList`

- Inputs: `status` (str | None), `source` (str | None), `company` (str | None), `limit` (int)
- Output: Returns `SecurityIncidentList`.
- Why: `intelligence_incidents` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `SecurityIncidentList`, `get_settings`, `SecurityIncidentOut.model_validate`, `incident_to_api`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async intelligence_incident_detail(incident_id: str) -> SecurityIncidentOut`

- Inputs: `incident_id` (str)
- Output: Returns `SecurityIncidentOut`.
- Why: `intelligence_incident_detail` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `SecurityIncidentOut.model_validate`, `get_incident`, `HTTPException`, `incident_to_api`, `get_settings`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async intelligence_watch_targets(target_type: str | None = None, enabled: bool | None = None, limit: int = Query(default=100, ge=1, le=500)) -> WatchTargetList`

- Inputs: `target_type` (str | None), `enabled` (bool | None), `limit` (int)
- Output: Returns `WatchTargetList`.
- Why: `intelligence_watch_targets` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `WatchTargetList`, `get_settings`, `WatchTargetOut.model_validate`, `watch_target_to_api`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async intelligence_create_watch_target(payload: WatchTargetCreate, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> WatchTargetOut`

- Inputs: `payload` (WatchTargetCreate), `idempotency_key` (str), `actor` (str)
- Output: Returns `WatchTargetOut`.
- Why: `intelligence_create_watch_target` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `WatchTargetOut.model_validate`, `create_watch_target`, `watch_target_to_api`, `get_settings`; uses idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async intelligence_patch_watch_target(watch_target_id: str, payload: WatchTargetPatch, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> WatchTargetOut`

- Inputs: `watch_target_id` (str), `payload` (WatchTargetPatch), `idempotency_key` (str), `actor` (str)
- Output: Returns `WatchTargetOut`.
- Why: `intelligence_patch_watch_target` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `WatchTargetOut.model_validate`, `HTTPException`, `watch_target_to_api`, `patch_watch_target`, `get_settings`; uses idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async intelligence_promote_incident_to_watchlist(incident_id: str, request: IncidentWatchPromotionRequest, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> WatchTargetOut`

- Inputs: `incident_id` (str), `request` (IncidentWatchPromotionRequest), `idempotency_key` (str), `actor` (str)
- Output: Returns `WatchTargetOut`.
- Why: `intelligence_promote_incident_to_watchlist` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `WatchTargetOut.model_validate`, `promote_incident_to_watchlist`, `HTTPException`, `watch_target_to_api`, `get_settings`; uses optimistic version checks, idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async crm_sync_account(payload: dict[str, object]) -> dict[str, object]`

- Inputs: `payload` (dict[str, object])
- Output: Returns `dict[str, object]`.
- Why: `crm_sync_account` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `new_event`, `event.model_dump`, `payload.get`, `uuid4`; uses outbox/event emission, serialization/projection.
- Side effects: adds outbox/event records; runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async crm_export_start(request: CrmExportCreateRequest, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> CrmExportBatchOut`

- Inputs: `request` (CrmExportCreateRequest), `idempotency_key` (str), `actor` (str)
- Output: Returns `CrmExportBatchOut`.
- Why: `crm_export_start` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `start_crm_export`, `HTTPException`, `get_settings`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async crm_export_detail(batch_id: str) -> CrmExportBatchOut`

- Inputs: `batch_id` (str)
- Output: Returns `CrmExportBatchOut`.
- Why: `crm_export_detail` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_crm_export_batch`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async crm_export_retry_failed(batch_id: str, request: CrmExportRetryRequest | None = None, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> CrmExportBatchOut`

- Inputs: `batch_id` (str), `request` (CrmExportRetryRequest | None), `idempotency_key` (str), `actor` (str)
- Output: Returns `CrmExportBatchOut`.
- Why: `crm_export_retry_failed` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `HTTPException`, `retry_failed_crm_export_items`, `get_settings`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async domain_enrichment(request: DomainEnrichmentRequest) -> Any`

- Inputs: `request` (DomainEnrichmentRequest)
- Output: Returns `Any`.
- Why: `domain_enrichment` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `enrich_domain`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async enrichment_create_entity_resolution(request: EntityResolutionCreate, idempotency_key: str = Header(alias='Idempotency-Key')) -> EntityResolutionOut`

- Inputs: `request` (EntityResolutionCreate), `idempotency_key` (str)
- Output: Returns `EntityResolutionOut`.
- Why: `enrichment_create_entity_resolution` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `entity_resolution_to_model`, `create_entity_resolution`, `get_settings`; uses idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async enrichment_entity_resolutions(status: str | None = None, origin_type: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> EntityResolutionList`

- Inputs: `status` (str | None), `origin_type` (str | None), `limit` (int)
- Output: Returns `EntityResolutionList`.
- Why: `enrichment_entity_resolutions` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `EntityResolutionList`, `get_settings`, `entity_resolution_to_model`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async enrichment_create_contact_candidate(request: ContactEnrichmentCreate, idempotency_key: str = Header(alias='Idempotency-Key')) -> ContactEnrichmentOut`

- Inputs: `request` (ContactEnrichmentCreate), `idempotency_key` (str)
- Output: Returns `ContactEnrichmentOut`.
- Why: `enrichment_create_contact_candidate` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `contact_candidate_to_model`, `create_contact_enrichment_candidate`, `get_settings`; uses idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async enrichment_contact_candidates(status: str | None = None, origin_type: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> ContactEnrichmentList`

- Inputs: `status` (str | None), `origin_type` (str | None), `limit` (int)
- Output: Returns `ContactEnrichmentList`.
- Why: `enrichment_contact_candidates` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `ContactEnrichmentList`, `get_settings`, `contact_candidate_to_model`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async email_candidates(request: EmailCandidateRequest) -> Any`

- Inputs: `request` (EmailCandidateRequest)
- Output: Returns `Any`.
- Why: `email_candidates` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `candidate.model_dump`, `generate_email_candidates`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async email_persist_candidates(request: EmailCandidatePersistRequest, idempotency_key: str = Header(alias='Idempotency-Key')) -> EmailCandidatePersistResult`

- Inputs: `request` (EmailCandidatePersistRequest), `idempotency_key` (str)
- Output: Returns `EmailCandidatePersistResult`.
- Why: `email_persist_candidates` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `EmailCandidatePersistResult`, `persist_email_candidates`, `HTTPException`, `email_candidate_to_model`, `get_settings`; uses idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async email_verify_batch(request: EmailVerifyBatchRequest) -> EmailVerifyBatchResult`

- Inputs: `request` (EmailVerifyBatchRequest)
- Output: Returns `EmailVerifyBatchResult`.
- Why: `email_verify_batch` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `EmailVerifyBatchResult`, `verify_email_candidates`, `get_settings`, `email_candidate_to_model`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async email_verify(payload: dict[str, object]) -> dict[str, object]`

- Inputs: `payload` (dict[str, object])
- Output: Returns `dict[str, object]`.
- Why: `email_verify` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async lead_score(request: ScoreRequest) -> Any`

- Inputs: `request` (ScoreRequest)
- Output: Returns `Any`.
- Why: `lead_score` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `score_lead`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async candidate_score(request: CandidateScoreRequest, idempotency_key: str = Header(alias='Idempotency-Key')) -> CandidateScoreOut`

- Inputs: `request` (CandidateScoreRequest), `idempotency_key` (str)
- Output: Returns `CandidateScoreOut`.
- Why: `candidate_score` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `candidate_score_to_model`, `create_candidate_score`, `get_settings`; uses idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async sequence_eligibility(request: SequenceEligibilityRequest) -> Any`

- Inputs: `request` (SequenceEligibilityRequest)
- Output: Returns `Any`.
- Why: `sequence_eligibility` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `evaluate_sequence_eligibility`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async sequence_create(request: SequenceCreateRequest, idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> SequenceOut`

- Inputs: `request` (SequenceCreateRequest), `idempotency_key` (str | None), `actor` (str)
- Output: Returns `SequenceOut`.
- Why: `sequence_create` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `create_sequence`, `HTTPException`, `get_settings`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async sequence_enrollment_create(request: SequenceEnrollmentCreateRequest, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> SequenceEnrollmentOut`

- Inputs: `request` (SequenceEnrollmentCreateRequest), `idempotency_key` (str), `actor` (str)
- Output: Returns `SequenceEnrollmentOut`.
- Why: `sequence_enrollment_create` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `create_sequence_enrollment`, `HTTPException`, `get_settings`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async sequence_enrollment_list(status: str | None = Query(default=None), limit: int = Query(default=100, ge=1, le=500)) -> SequenceEnrollmentList`

- Inputs: `status` (str | None), `limit` (int)
- Output: Returns `SequenceEnrollmentList`.
- Why: `sequence_enrollment_list` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async sequence_enrollment_detail(enrollment_id: str) -> SequenceEnrollmentOut`

- Inputs: `enrollment_id` (str)
- Output: Returns `SequenceEnrollmentOut`.
- Why: `sequence_enrollment_detail` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_sequence_enrollment`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async sequence_enrollment_pause(enrollment_id: str, request: SequenceEnrollmentActionRequest, actor: str = Header(default='system', alias='X-Actor')) -> SequenceEnrollmentOut`

- Inputs: `enrollment_id` (str), `request` (SequenceEnrollmentActionRequest), `actor` (str)
- Output: Returns `SequenceEnrollmentOut`.
- Why: `sequence_enrollment_pause` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `HTTPException`, `pause_sequence_enrollment`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async sequence_enrollment_resume(enrollment_id: str, request: SequenceEnrollmentActionRequest, actor: str = Header(default='system', alias='X-Actor')) -> SequenceEnrollmentOut`

- Inputs: `enrollment_id` (str), `request` (SequenceEnrollmentActionRequest), `actor` (str)
- Output: Returns `SequenceEnrollmentOut`.
- Why: `sequence_enrollment_resume` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `HTTPException`, `resume_sequence_enrollment`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async sequence_enrollment_cancel(enrollment_id: str, request: SequenceEnrollmentActionRequest, actor: str = Header(default='system', alias='X-Actor')) -> SequenceEnrollmentOut`

- Inputs: `enrollment_id` (str), `request` (SequenceEnrollmentActionRequest), `actor` (str)
- Output: Returns `SequenceEnrollmentOut`.
- Why: `sequence_enrollment_cancel` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `HTTPException`, `cancel_sequence_enrollment`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async sequence_unsubscribe(request: UnsubscribeRequest, idempotency_key: str = Header(alias='Idempotency-Key')) -> Any`

- Inputs: `request` (UnsubscribeRequest), `idempotency_key` (str)
- Output: Returns `Any`.
- Why: `sequence_unsubscribe` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `process_unsubscribe`, `get_settings`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async calendar_availability(request: CalendarAvailabilityRequest) -> CalendarAvailabilityResult`

- Inputs: `request` (CalendarAvailabilityRequest)
- Output: Returns `CalendarAvailabilityResult`.
- Why: `calendar_availability` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_calendar_availability`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async meeting_create(request: MeetingCreateRequest, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> MeetingHandoffOut`

- Inputs: `request` (MeetingCreateRequest), `idempotency_key` (str), `actor` (str)
- Output: Returns `MeetingHandoffOut`.
- Why: `meeting_create` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `create_meeting`, `HTTPException`, `get_settings`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async meeting_list(status: str | None = None, crm_target_id: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> MeetingHandoffList`

- Inputs: `status` (str | None), `crm_target_id` (str | None), `limit` (int)
- Output: Returns `MeetingHandoffList`.
- Why: `meeting_list` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async meeting_detail(meeting_id: str) -> MeetingHandoffOut`

- Inputs: `meeting_id` (str)
- Output: Returns `MeetingHandoffOut`.
- Why: `meeting_detail` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_meeting`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async meeting_generate_prep_packet(meeting_id: str, idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> MeetingHandoffOut`

- Inputs: `meeting_id` (str), `idempotency_key` (str | None), `actor` (str)
- Output: Returns `MeetingHandoffOut`.
- Why: `meeting_generate_prep_packet` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `generate_meeting_prep_packet`, `HTTPException`, `get_settings`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async meeting_record_outcome(meeting_id: str, request: MeetingOutcomeRequest, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> MeetingHandoffOut`

- Inputs: `meeting_id` (str), `request` (MeetingOutcomeRequest), `idempotency_key` (str), `actor` (str)
- Output: Returns `MeetingHandoffOut`.
- Why: `meeting_record_outcome` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `record_meeting_outcome`, `HTTPException`, `get_settings`; uses idempotency lookup.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async meeting_cancel(meeting_id: str, request: MeetingActionRequest, actor: str = Header(default='system', alias='X-Actor')) -> MeetingHandoffOut`

- Inputs: `meeting_id` (str), `request` (MeetingActionRequest), `actor` (str)
- Output: Returns `MeetingHandoffOut`.
- Why: `meeting_cancel` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `HTTPException`, `cancel_meeting`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async meeting_retry_sync(meeting_id: str, actor: str = Header(default='system', alias='X-Actor')) -> MeetingHandoffOut`

- Inputs: `meeting_id` (str), `actor` (str)
- Output: Returns `MeetingHandoffOut`.
- Why: `meeting_retry_sync` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `retry_meeting_crm_sync`, `HTTPException`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`.

##### `async prep_packet(request: PrepPacketRequest) -> Any`

- Inputs: `request` (PrepPacketRequest)
- Output: Returns `Any`.
- Why: `prep_packet` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `build_prep_packet`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async suppression_create(request: SuppressionCreate, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> SuppressionOut`

- Inputs: `request` (SuppressionCreate), `idempotency_key` (str), `actor` (str)
- Output: Returns `SuppressionOut`.
- Why: `suppression_create` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `suppression_to_model`, `create_suppression`, `get_settings`; uses idempotency lookup, policy validation, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async suppression_check(request: SuppressionCheckRequest) -> Any`

- Inputs: `request` (SuppressionCheckRequest)
- Output: Returns `Any`.
- Why: `suppression_check` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `evaluate_suppression_with_store`, `get_settings`; uses policy validation.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async review_candidates(status: str | None = 'open', candidate_type: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> ReviewCandidateList`

- Inputs: `status` (str | None), `candidate_type` (str | None), `limit` (int)
- Output: Returns `ReviewCandidateList`.
- Why: `review_candidates` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `ReviewCandidateList`, `get_settings`, `review_candidate_to_model`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async review_candidate_approve(candidate_id: str, request: ReviewDecisionRequest, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> ReviewDecisionOut`

- Inputs: `candidate_id` (str), `request` (ReviewDecisionRequest), `idempotency_key` (str), `actor` (str)
- Output: Returns `ReviewDecisionOut`.
- Why: `review_candidate_approve` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `review_decision_to_model`, `HTTPException`, `approve_review_candidate`, `get_settings`; uses idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async review_candidate_reject(candidate_id: str, request: ReviewDecisionRequest, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> ReviewDecisionOut`

- Inputs: `candidate_id` (str), `request` (ReviewDecisionRequest), `idempotency_key` (str), `actor` (str)
- Output: Returns `ReviewDecisionOut`.
- Why: `review_candidate_reject` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `review_decision_to_model`, `HTTPException`, `reject_review_candidate`, `get_settings`; uses idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async review_candidates_bulk_decision(request: BulkReviewDecisionRequest, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> BulkReviewDecisionResult`

- Inputs: `request` (BulkReviewDecisionRequest), `idempotency_key` (str), `actor` (str)
- Output: Returns `BulkReviewDecisionResult`.
- Why: `review_candidates_bulk_decision` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `BulkReviewDecisionResult`, `bulk_decide_review_candidates`, `HTTPException`, `review_decision_to_model`, `get_settings`; uses idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async review_crm_targets(status: str | None = None, target_type: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> CrmTargetList`

- Inputs: `status` (str | None), `target_type` (str | None), `limit` (int)
- Output: Returns `CrmTargetList`.
- Why: `review_crm_targets` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Query`, `CrmTargetList`, `get_settings`, `crm_target_to_model`; uses serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `async governance_corroborate_incident(incident_id: str, request: IncidentDecisionRequest, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> ReviewDecisionOut`

- Inputs: `incident_id` (str), `request` (IncidentDecisionRequest), `idempotency_key` (str), `actor` (str)
- Output: Returns `ReviewDecisionOut`.
- Why: `governance_corroborate_incident` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `review_decision_to_model`, `HTTPException`, `corroborate_incident`, `get_settings`; uses idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async governance_reject_incident(incident_id: str, request: IncidentDecisionRequest, idempotency_key: str = Header(alias='Idempotency-Key'), actor: str = Header(default='system', alias='X-Actor')) -> ReviewDecisionOut`

- Inputs: `incident_id` (str), `request` (IncidentDecisionRequest), `idempotency_key` (str), `actor` (str)
- Output: Returns `ReviewDecisionOut`.
- Why: `governance_reject_incident` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `Header`, `review_decision_to_model`, `HTTPException`, `reject_incident`, `get_settings`; uses idempotency lookup, serialization/projection.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: raises `HTTPException`; catches provider or validation errors and maps them to the module contract.

##### `async kpi_catalog(operator: ReportingOperatorContext = REPORTING_OPERATOR_CONTEXT) -> ReportingKpiCatalog`

- Inputs: `operator` (ReportingOperatorContext)
- Output: Returns `ReportingKpiCatalog`.
- Why: `kpi_catalog` provides the src/ghostrecon/service_apps/routers.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `get_reporting_kpi_catalog`, `get_settings`.
- Side effects: runs asynchronously and may await database or provider operations.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

### `src/ghostrecon/service_apps/factory.py`

#### Module Functions

##### `build_app(settings: Settings | None = None) -> FastAPI`

- Inputs: `settings` (Settings | None)
- Output: Returns `FastAPI`.
- Why: `build_app` derives a stable request, key, or projection object from richer inputs.
- How: It calls `create_base_app`, `ROUTERS.get`, `app.include_router`, `get_settings`, `join`, `RuntimeError`, `create_console_dash_app`, `app.mount`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `RuntimeError`.

### `src/ghostrecon/service_apps/entrypoint.py`

No classes or functions are defined in this module.

### `src/ghostrecon/service_apps/runtime.py`

No classes or functions are defined in this module.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_event_routes.py`
- `tests/unit/test_incident_routes.py`
- `tests/unit/test_reporting_routes.py`
- `tests/unit/test_enrichment_routes.py`
