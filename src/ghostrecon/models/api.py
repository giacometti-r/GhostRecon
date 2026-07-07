from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class LeadSourceType(StrEnum):
    CRM = "crm"
    FORM = "form"
    CSV = "csv"
    CRAWL = "crawl"
    MANUAL = "manual"
    CYBER_EVENT = "cyber_event"
    SECURITY_INCIDENT = "security_incident"


class OriginType(StrEnum):
    CYBER_EVENT = "cyber_event"
    EVENT_PARTICIPANT = "event_participant"
    SECURITY_INCIDENT = "security_incident"
    MANUAL = "manual"


class EntityResolutionStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"


class ContactEnrichmentStatus(StrEnum):
    PENDING = "pending"
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class ContactRoleScope(StrEnum):
    SECURITY = "security"
    IT = "it"
    RISK = "risk"
    COMMUNICATIONS = "communications"
    OTHER = "other"
    UNKNOWN = "unknown"


class EmailVerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    INVALID = "invalid"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class ReviewCandidateType(StrEnum):
    ENTITY_RESOLUTION = "entity_resolution"
    CONTACT_ENRICHMENT = "contact_enrichment"
    EMAIL_VERIFICATION = "email_verification"
    SCORING = "scoring"
    INCIDENT_CORROBORATION = "incident_corroboration"


class ReviewCandidateStatus(StrEnum):
    OPEN = "open"
    SUPERSEDED = "superseded"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecisionAction(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class CandidateScoreRoute(StrEnum):
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    CRM_TARGET_REVIEW = "crm_target_review"


class CrmTargetStatus(StrEnum):
    PENDING_EXPORT = "pending_export"
    INVALIDATED = "invalidated"
    EXPORTED = "exported"


class CrmExportBatchStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RECONCILING = "reconciling"


class CrmExportItemStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"
    SKIPPED_POLICY = "skipped_policy"
    RECONCILED = "reconciled"


class CrmExportOperation(StrEnum):
    UPSERT_RECORD = "upsert_record"
    ADD_TO_LIST = "add_to_list"


class SequenceStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class SequenceEnrollmentStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELED = "canceled"
    SUPPRESSED = "suppressed"
    FAILED = "failed"


class OutboundEmailStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"
    SKIPPED_POLICY = "skipped_policy"


class InboundEmailEventType(StrEnum):
    REPLY = "reply"
    BOUNCE = "bounce"
    UNSUBSCRIBE = "unsubscribe"


class MeetingStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED_SYNC = "failed_sync"


class MeetingOutcomeStatus(StrEnum):
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"
    DISQUALIFIED = "disqualified"


class MeetingCrmSyncStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"


class MeetingFollowUpTaskStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    CANCELED = "canceled"


class SourceKind(StrEnum):
    EVENT = "event"
    INCIDENT = "incident"
    CRM = "crm"


class SourceAdapterType(StrEnum):
    HTTP_PAGE = "http_page"
    SCHEMA_ORG = "schema_org"
    ICS = "ics"
    RSS_ATOM = "rss_atom"
    SCHEDULED_QUERY = "scheduled_query"
    GDELT_DOC = "gdelt_doc"


class SourcePolicyState(StrEnum):
    ALLOWED = "allowed"
    UNKNOWN = "unknown"
    PROHIBITED = "prohibited"


class ParticipantReuseState(StrEnum):
    ALLOWED = "allowed"
    UNKNOWN = "unknown"
    PROHIBITED = "prohibited"


class ContentStoragePolicy(StrEnum):
    METADATA_ONLY = "metadata_only"
    METADATA_EXCERPT = "metadata_excerpt"
    LICENSED_BODY = "licensed_body"


class SourceOperatingState(StrEnum):
    ENABLED = "enabled"
    PAUSED = "paused"
    DEGRADED = "degraded"


class SourceHealthStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class RawSourceParseStatus(StrEnum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class DuplicateState(StrEnum):
    CANONICAL = "canonical"
    DUPLICATE = "duplicate"
    QUARANTINED = "quarantined"


class EventFormat(StrEnum):
    PHYSICAL = "physical"
    VIRTUAL = "virtual"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class EventCanonicalState(StrEnum):
    CANONICAL = "canonical"
    DUPLICATE = "duplicate"
    NEEDS_REVIEW = "needs_review"


class EventTimezoneStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"


class EventParticipantType(StrEnum):
    SPEAKER = "speaker"
    SPONSOR = "sponsor"
    ORGANIZER = "organizer"
    ATTENDEE = "attendee"
    UNKNOWN = "unknown"


class CyberEventOut(BaseModel):
    id: str
    name: str
    event_series_key: str
    external_id: str | None = None
    canonical_url: str | None = None
    original_start: str | None = None
    original_end: str | None = None
    source_timezone: str | None = None
    iana_timezone: str | None = None
    timezone_status: EventTimezoneStatus = EventTimezoneStatus.RESOLVED
    starts_at_utc: datetime | None = None
    ends_at_utc: datetime | None = None
    event_format: EventFormat = EventFormat.UNKNOWN
    venue_name: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    virtual_url: str | None = None
    topics: list[object] = []
    organizers: list[object] = []
    confidence: int = Field(ge=0, le=100)
    canonical_state: EventCanonicalState = EventCanonicalState.CANONICAL
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    created_at: datetime
    updated_at: datetime


class CyberEventList(BaseModel):
    events: list[CyberEventOut]


class EventParticipantOut(BaseModel):
    id: str
    cyber_event_id: str
    source_definition_id: str | None = None
    source_item_id: str | None = None
    source_participant_id: str | None = None
    published_name: str
    organization: str | None = None
    published_role: str | None = None
    participant_type: EventParticipantType = EventParticipantType.UNKNOWN
    profile_url: str | None = None
    reuse_state: ParticipantReuseState = ParticipantReuseState.UNKNOWN
    reuse_evidence: dict[str, object] = {}
    contact_extraction_allowed: bool
    crm_export_allowed: bool
    resolution_confidence: int = Field(ge=0, le=100)
    created_at: datetime
    updated_at: datetime


class EventParticipantList(BaseModel):
    participants: list[EventParticipantOut]


class SecurityIncidentStatus(StrEnum):
    CANDIDATE = "candidate"
    CORROBORATED = "corroborated"
    REJECTED = "rejected"


class IncidentCanonicalState(StrEnum):
    CANONICAL = "canonical"
    DUPLICATE = "duplicate"
    NEEDS_REVIEW = "needs_review"


class CorroborationMethod(StrEnum):
    NONE = "none"
    AUTHORITATIVE_DISCLOSURE = "authoritative_disclosure"
    INDEPENDENT_SOURCES = "independent_sources"
    ANALYST_DECISION = "analyst_decision"


class WatchTargetType(StrEnum):
    COMPANY = "company"
    DOMAIN = "domain"
    INCIDENT = "incident"
    EVENT_SERIES = "event_series"
    TOPIC = "topic"


class NewsArticleOut(BaseModel):
    id: str
    canonical_url: str
    publisher: str | None = None
    title: str
    permitted_excerpt: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    original_language: str | None = None
    translated_title: str | None = None
    translation_metadata: dict[str, object] = {}
    content_hash: str
    syndication_cluster_key: str
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    created_at: datetime
    updated_at: datetime


class SecurityIncidentOut(BaseModel):
    id: str
    status: SecurityIncidentStatus = SecurityIncidentStatus.CANDIDATE
    title: str
    affected_companies: list[object] = []
    affected_domains: list[object] = []
    incident_type: str | None = None
    attack_vector: str | None = None
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    geography: list[object] = []
    languages: list[object] = []
    confidence: int = Field(ge=0, le=100)
    evidence_article_ids: list[object] = []
    evidence_source_item_ids: list[object] = []
    evidence_families: list[object] = []
    corroboration_method: CorroborationMethod = CorroborationMethod.NONE
    analyst_decision_ref: str | None = None
    canonical_state: IncidentCanonicalState = IncidentCanonicalState.CANONICAL
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    created_at: datetime
    updated_at: datetime


class SecurityIncidentList(BaseModel):
    incidents: list[SecurityIncidentOut]


class WatchTargetOut(BaseModel):
    id: str
    target_type: WatchTargetType
    canonical_target_key: str
    display_name: str
    query_config: dict[str, object] = {}
    enabled: bool
    owner: str | None = None
    origin_incident_id: str | None = None
    created_by: str
    version: int
    created_at: datetime
    updated_at: datetime


class WatchTargetList(BaseModel):
    watch_targets: list[WatchTargetOut]


class WatchTargetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: WatchTargetType
    canonical_target_key: str
    display_name: str
    query_config: dict[str, object] = {}
    owner: str | None = None
    origin_incident_id: str | None = None


class WatchTargetPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    display_name: str | None = None
    query_config: dict[str, object] | None = None
    owner: str | None = None
    version: int


class EntityResolutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_type: OriginType
    origin_id: str
    entity_kind: str = "organization"
    organization_name: str | None = None
    domain: str | None = None
    source_definition_id: str | None = None
    source_item_ids: list[str] = []
    policy_snapshot: dict[str, object] = {}


class EntityResolutionOut(BaseModel):
    id: str
    origin_type: OriginType
    origin_id: str
    entity_kind: str
    input_name: str | None = None
    input_domain: str | None = None
    resolved_account_id: str | None = None
    resolved_name: str | None = None
    resolved_domain: str | None = None
    status: EntityResolutionStatus
    confidence: int = Field(ge=0, le=100)
    alternatives: list[object] = []
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    policy_snapshot: dict[str, object] = {}
    review_reason: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class EntityResolutionList(BaseModel):
    cases: list[EntityResolutionOut]


class ContactEnrichmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_type: OriginType
    origin_id: str
    published_name: str
    organization: str | None = None
    title: str | None = None
    role_scope: ContactRoleScope = ContactRoleScope.UNKNOWN
    domain: str | None = None
    entity_resolution_case_id: str | None = None
    account_id: str | None = None
    profile_url: str | None = None
    source_url: str | None = None
    reuse_state: ParticipantReuseState = ParticipantReuseState.UNKNOWN
    source_definition_id: str | None = None
    source_item_ids: list[str] = []
    policy_snapshot: dict[str, object] = {}
    candidate_payload: dict[str, object] = {}
    breached_data_source: bool = False


class ContactEnrichmentOut(BaseModel):
    id: str
    entity_resolution_case_id: str | None = None
    account_id: str | None = None
    contact_id: str | None = None
    origin_type: OriginType
    origin_id: str
    published_name: str
    organization: str | None = None
    title: str | None = None
    role_scope: ContactRoleScope
    domain: str | None = None
    profile_url: str | None = None
    source_url: str | None = None
    status: ContactEnrichmentStatus
    eligibility_reason: str | None = None
    reuse_state: ParticipantReuseState
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    policy_snapshot: dict[str, object] = {}
    candidate_payload: dict[str, object] = {}
    review_reason: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class ContactEnrichmentList(BaseModel):
    candidates: list[ContactEnrichmentOut]


class EmailCandidatePersistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_candidate_id: str | None = None
    contact_id: str | None = None
    full_name: str | None = None
    domain: str
    origin_type: OriginType | None = None
    origin_id: str | None = None
    source_definition_id: str | None = None
    source_item_ids: list[str] = []
    policy_snapshot: dict[str, object] = {}
    known_patterns: list[str] = []


class EmailCandidateRecordOut(BaseModel):
    id: str
    contact_id: str | None = None
    email: EmailStr
    pattern: str
    verification_status: EmailVerificationStatus
    verification_payload: dict[str, object] = {}
    verification_checked_at: datetime | None = None
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    origin_type: OriginType | None = None
    origin_id: str | None = None
    policy_snapshot: dict[str, object] = {}
    review_status: str = "not_required"
    review_reason: str | None = None
    version: int
    created_at: datetime


class EmailCandidatePersistResult(BaseModel):
    candidates: list[EmailCandidateRecordOut]


class EmailVerifyBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_ids: list[str] = []
    verification_results: dict[str, dict[str, object]] = {}


class EmailVerifyBatchResult(BaseModel):
    candidates: list[EmailCandidateRecordOut]


class ReviewCandidateOut(BaseModel):
    id: str
    candidate_type: ReviewCandidateType
    target_type: str
    target_id: str
    origin_type: OriginType | None = None
    origin_id: str | None = None
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    status: ReviewCandidateStatus
    reason_code: str
    reason: str | None = None
    evidence_summary: dict[str, object] = {}
    policy_snapshot: dict[str, object] = {}
    policy_snapshot_hash: str | None = None
    sla_due_at: datetime | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class ReviewCandidateList(BaseModel):
    candidates: list[ReviewCandidateOut]


class SourceDefinitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source_kind: SourceKind
    adapter_type: SourceAdapterType
    base_url: str
    owner: str | None = None
    query_scope: dict[str, object] = {}
    freshness_slo_seconds: int = Field(default=86400, ge=60)
    polling_interval_seconds: int | None = Field(default=None, ge=60)
    policy_state: SourcePolicyState = SourcePolicyState.UNKNOWN
    participant_reuse_state: ParticipantReuseState = ParticipantReuseState.UNKNOWN
    content_storage_policy: ContentStoragePolicy = ContentStoragePolicy.METADATA_EXCERPT
    enabled: bool = True


class RawSourceItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_definition_id: str
    canonical_url: str
    content_hash: str
    external_id: str | None = None
    retrieved_at: datetime | None = None
    published_at: datetime | None = None
    original_language: str | None = None
    source_timezone: str | None = None
    raw_metadata: dict[str, object] = {}
    permitted_excerpt: str | None = None
    parse_status: RawSourceParseStatus = RawSourceParseStatus.PENDING
    idempotency_key: str


class SourceHealth(BaseModel):
    source_definition_id: str
    name: str
    source_kind: str
    adapter_type: str
    policy_state: str
    participant_reuse_state: str
    content_storage_policy: str
    enabled: bool
    operating_state: str
    freshness_status: SourceHealthStatus
    freshness_slo_seconds: int
    freshness_lag_seconds: int | None = None
    checkpoint_state: dict[str, object] = {}
    last_fetch_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0


class SourceHealthList(BaseModel):
    sources: list[SourceHealth]


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class AccountIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    company_name: str
    crm_account_id: str | None = None
    hq_country: str | None = None
    employee_count: int | None = Field(default=None, ge=0)
    industry: str | None = None
    named_account_flag: bool = False


class ContactIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str | None = None
    full_name: str
    title: str | None = None
    email: EmailStr | None = None
    linkedin_url: HttpUrl | None = None
    source_url: HttpUrl | None = None


class DomainEnrichmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    crawl: bool = True
    max_pages: int = Field(default=20, ge=1, le=100)


class DomainEnrichmentResult(BaseModel):
    domain: str
    mx_records: list[str] = []
    nameservers: list[str] = []
    website_title: str | None = None
    security_signals: list[dict[str, object]] = []
    discovered_contacts: list[dict[str, object]] = []


class EmailCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str
    domain: str
    known_patterns: list[str] = []


class EmailCandidate(BaseModel):
    email: EmailStr
    pattern: str


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account: dict[str, object]
    contact: dict[str, object] | None = None
    signals: list[dict[str, object]] = []


class ScoreResult(BaseModel):
    fit_score: int = Field(ge=0, le=100)
    intent_score: int = Field(ge=0, le=100)
    composite_score: int = Field(ge=0, le=100)
    threshold_met: bool
    reasons: list[str]


class CandidateScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: str
    target_id: str
    origin_type: OriginType | None = None
    origin_id: str | None = None
    account: dict[str, object] = {}
    contact: dict[str, object] | None = None
    signals: list[dict[str, object]] = []
    evidence: dict[str, object] = {}
    source_definition_id: str | None = None
    source_item_ids: list[str] = []
    policy_snapshot: dict[str, object] = {}


class CandidateScoreOut(BaseModel):
    id: str | None = None
    target_type: str
    target_id: str
    origin_type: OriginType | None = None
    origin_id: str | None = None
    config_version: str
    fit_score: int = Field(ge=0, le=100)
    relevance_score: int = Field(ge=0, le=100)
    recency_score: int = Field(ge=0, le=100)
    confidence_score: int = Field(ge=0, le=100)
    evidence_score: int = Field(ge=0, le=100)
    composite_score: int = Field(ge=0, le=100)
    route: CandidateScoreRoute
    reasons: list[str]
    policy_blockers: list[str] = []
    policy_snapshot_hash: str
    created_at: datetime | None = None


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    reason_code: str
    reason: str | None = None
    policy_snapshot_hash: str | None = None
    evidence_snapshot: dict[str, object] = {}
    target_scope: str = "crm_export"


class BulkReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_ids: list[str] = Field(min_length=1, max_length=100)
    decision: ReviewDecisionAction
    candidate_versions: dict[str, int]
    reason_code: str
    reason: str | None = None
    policy_snapshot_hash: str | None = None
    evidence_snapshot: dict[str, object] = {}


class ReviewDecisionOut(BaseModel):
    id: str
    review_candidate_id: str | None = None
    target_type: str
    target_id: str
    decision: ReviewDecisionAction
    actor: str
    reason_code: str
    reason: str | None = None
    policy_snapshot_hash: str | None = None
    created_at: datetime


class BulkReviewDecisionResult(BaseModel):
    decisions: list[ReviewDecisionOut]


class CrmTargetOut(BaseModel):
    id: str
    review_candidate_id: str | None = None
    review_decision_id: str | None = None
    target_type: str
    target_id: str
    origin_type: OriginType | None = None
    origin_id: str | None = None
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    status: CrmTargetStatus
    export_status: str = "not_exported"
    policy_snapshot: dict[str, object] = {}
    approval_snapshot: dict[str, object] = {}
    version: int
    created_at: datetime
    updated_at: datetime


class CrmTargetList(BaseModel):
    crm_targets: list[CrmTargetOut]


class CrmExportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crm_target_ids: list[str] = Field(min_length=1, max_length=100)
    provider: str = "attio"
    workspace_id: str | None = None
    reason: str | None = None


class CrmExportRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_ids: list[str] = []


class CrmExportItemOut(BaseModel):
    id: str
    batch_id: str
    crm_target_id: str
    target_type: str
    target_id: str
    operation: CrmExportOperation
    dependency_item_ids: list[object] = []
    provider_object: str
    provider_record_id: str | None = None
    provider_list_id: str | None = None
    provider_list_entry_id: str | None = None
    stable_match_key: str
    status: CrmExportItemStatus
    attempt_count: int
    last_error: str | None = None
    retry_after_seconds: int | None = None
    reconciliation_state: str = "not_required"
    created_at: datetime
    updated_at: datetime


class CrmExportBatchOut(BaseModel):
    id: str
    provider: str
    workspace_id: str | None = None
    requested_by: str
    status: CrmExportBatchStatus
    crm_target_ids: list[object] = []
    selection_hash: str
    idempotency_key: str
    counts: dict[str, object] = {}
    reconciliation_summary: dict[str, object] = {}
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[CrmExportItemOut] = []


class DashboardRole(StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    GOVERNANCE_REVIEWER = "governance_reviewer"
    ADMINISTRATOR = "administrator"


class ReportingOperatorContext(BaseModel):
    actor: str = "system"
    role: DashboardRole = DashboardRole.VIEWER


class ReportingMetadata(BaseModel):
    generated_at: datetime
    watermarks: dict[str, object] = {}
    projection_version: str
    stale: bool = False
    degraded_dependencies: list[str] = []


class ReportingEventList(BaseModel):
    metadata: ReportingMetadata
    events: list[CyberEventOut]
    next_cursor: str | None = None


class ReportingEventDetail(BaseModel):
    metadata: ReportingMetadata
    event: CyberEventOut


class ReportingIncidentList(BaseModel):
    metadata: ReportingMetadata
    incidents: list[SecurityIncidentOut]
    next_cursor: str | None = None


class ReportingIncidentDetail(BaseModel):
    metadata: ReportingMetadata
    incident: SecurityIncidentOut


class ReportingWatchTargetList(BaseModel):
    metadata: ReportingMetadata
    watch_targets: list[WatchTargetOut]
    next_cursor: str | None = None


class ReportingReviewQueue(BaseModel):
    metadata: ReportingMetadata
    candidates: list[ReviewCandidateOut]
    next_cursor: str | None = None


class ReportingCrmTargetList(BaseModel):
    metadata: ReportingMetadata
    crm_targets: list[CrmTargetOut]
    next_cursor: str | None = None


class ReportingSourceHealthList(BaseModel):
    metadata: ReportingMetadata
    sources: list[SourceHealth]
    next_cursor: str | None = None


class ReportingKpiCatalog(BaseModel):
    metadata: ReportingMetadata
    kpis: dict[str, list[str]]


class SuppressionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    domain: str | None = None
    contact_id: str | None = None
    channel: str = "email"
    target_type: str | None = None
    target_id: str | None = None
    reason: str
    source: str = "governance"
    active: bool = True
    expires_at: datetime | None = None
    policy_snapshot: dict[str, object] = {}


class SuppressionOut(BaseModel):
    id: str
    email: EmailStr | None = None
    domain: str | None = None
    contact_id: str | None = None
    channel: str
    target_type: str | None = None
    target_id: str | None = None
    reason: str
    source: str
    active: bool
    expires_at: datetime | None = None
    policy_snapshot: dict[str, object] = {}
    created_at: datetime


class IncidentDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    method: CorroborationMethod = CorroborationMethod.ANALYST_DECISION
    reason_code: str
    reason: str | None = None
    evidence_snapshot: dict[str, object] = {}
    policy_snapshot: dict[str, object] = {}


class SuppressionCheckRequest(BaseModel):
    email: EmailStr | None = None
    domain: str | None = None
    contact_id: str | None = None
    channel: str = "email"


class SuppressionCheckResult(BaseModel):
    allowed: bool
    reason: str | None = None


class PrepPacketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account: dict[str, object]
    contacts: list[dict[str, object]] = []
    signals: list[dict[str, object]] = []
    meeting_time: datetime | None = None


class PrepPacket(BaseModel):
    account_summary: str
    stakeholder_map: list[str]
    likely_security_priorities: list[str]
    suggested_questions: list[str]
    risks: list[str]


class MeetingAttendee(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    name: str | None = None
    optional: bool = False


class MeetingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crm_target_id: str
    sequence_enrollment_id: str | None = None
    account_id: str | None = None
    contact_id: str | None = None
    subject: str = Field(min_length=1, max_length=512)
    description: str | None = None
    location: str | None = None
    start_at: datetime
    end_at: datetime
    timezone: str = "UTC"
    attendees: list[MeetingAttendee] = []
    policy_snapshot: dict[str, object] = {}
    send_updates: bool | None = None


class MeetingActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class MeetingFollowUpTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=512)
    description: str | None = None
    owner: str | None = None
    due_at: datetime | None = None


class MeetingOutcomeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_status: MeetingOutcomeStatus = MeetingOutcomeStatus.COMPLETED
    outcome_notes: str | None = None
    next_steps: list[str] = []
    follow_up_tasks: list[MeetingFollowUpTaskCreate] = []


class CalendarAvailabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attendees: list[EmailStr] = Field(min_length=1, max_length=50)
    time_min: datetime
    time_max: datetime
    timezone: str = "UTC"


class CalendarBusySlot(BaseModel):
    start: datetime
    end: datetime


class CalendarAvailabilityResult(BaseModel):
    calendars: dict[str, list[CalendarBusySlot]]
    provider: str = "google"


class MeetingPrepPacketOut(BaseModel):
    id: str
    meeting_id: str
    account_summary: str
    stakeholder_map: list[object] = []
    likely_security_priorities: list[object] = []
    suggested_questions: list[object] = []
    risks: list[object] = []
    source_snapshot: dict[str, object] = {}
    generated_by: str
    created_at: datetime
    updated_at: datetime


class MeetingFollowUpTaskOut(BaseModel):
    id: str
    meeting_id: str
    title: str
    description: str | None = None
    owner: str | None = None
    due_at: datetime | None = None
    status: MeetingFollowUpTaskStatus
    crm_sync_status: MeetingCrmSyncStatus
    provider_task_id: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class MeetingHandoffOut(BaseModel):
    id: str
    crm_target_id: str | None = None
    sequence_enrollment_id: str | None = None
    account_id: str | None = None
    contact_id: str | None = None
    status: MeetingStatus
    subject: str
    description: str | None = None
    location: str | None = None
    start_at: datetime
    end_at: datetime
    timezone: str
    attendees: list[object] = []
    calendar_provider: str
    calendar_id: str | None = None
    provider_event_id: str | None = None
    provider_html_link: str | None = None
    outcome_status: MeetingOutcomeStatus | None = None
    outcome_notes: str | None = None
    next_steps: list[object] = []
    crm_sync_status: MeetingCrmSyncStatus
    crm_sync_error: str | None = None
    crm_retry_after_seconds: int | None = None
    policy_snapshot: dict[str, object] = {}
    version: int
    created_at: datetime
    updated_at: datetime
    prep_packet: MeetingPrepPacketOut | None = None
    follow_up_tasks: list[MeetingFollowUpTaskOut] = []


class MeetingHandoffList(BaseModel):
    meetings: list[MeetingHandoffOut]


class ReportingMeetingList(BaseModel):
    metadata: ReportingMetadata
    meetings: list[MeetingHandoffOut]
    next_cursor: str | None = None


class ReportingMeetingDetail(BaseModel):
    metadata: ReportingMetadata
    meeting: MeetingHandoffOut


class SequenceEligibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact: dict[str, object]
    score: ScoreResult
    suppression: SuppressionCheckResult


class SequenceEligibilityResult(BaseModel):
    eligible: bool
    next_action: str
    requires_approval: bool
    reasons: list[str]


class SequenceStepCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_order: int | None = Field(default=None, ge=1)
    delay_seconds: int = Field(default=0, ge=0)
    subject_template: str = Field(min_length=1, max_length=512)
    body_template: str = Field(min_length=1)
    channel: str = "email"


class SequenceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    owner_id: str | None = None
    channel: str = "email"
    rate_limit_policy: dict[str, object] = {}
    steps: list[SequenceStepCreate] = Field(min_length=1, max_length=20)


class SequenceStepOut(BaseModel):
    id: str
    sequence_id: str
    step_order: int
    channel: str
    delay_seconds: int
    subject_template: str
    body_template: str
    active: bool
    created_at: datetime
    updated_at: datetime


class SequenceOut(BaseModel):
    id: str
    name: str
    owner_id: str | None = None
    channel: str
    status: SequenceStatus
    rate_limit_policy: dict[str, object] = {}
    created_at: datetime
    updated_at: datetime
    steps: list[SequenceStepOut] = []


class SequenceEnrollmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_id: str
    crm_target_id: str
    contact_id: str | None = None
    account_id: str | None = None
    start_at: datetime | None = None
    outreach_approved: bool
    approval_reason: str = Field(min_length=1, max_length=500)
    policy_snapshot: dict[str, object] = {}


class SequenceEnrollmentActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class OutboundEmailOut(BaseModel):
    id: str
    enrollment_id: str
    sequence_step_id: str
    contact_id: str
    channel: str
    to_email: EmailStr
    from_email: EmailStr
    subject: str
    status: OutboundEmailStatus
    provider_message_id: str | None = None
    attempt_count: int
    last_error: str | None = None
    retry_after_seconds: int | None = None
    scheduled_at: datetime
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SequenceEnrollmentOut(BaseModel):
    id: str
    sequence_id: str
    crm_target_id: str
    contact_id: str
    account_id: str | None = None
    status: SequenceEnrollmentStatus
    approval_actor: str
    approval_reason: str
    current_step_order: int
    next_step_at: datetime | None = None
    pause_reason: str | None = None
    policy_snapshot: dict[str, object] = {}
    version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    outbound_emails: list[OutboundEmailOut] = []


class SequenceEnrollmentList(BaseModel):
    enrollments: list[SequenceEnrollmentOut]


class InboundEmailEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: InboundEmailEventType
    from_email: EmailStr | None = None
    to_email: EmailStr | None = None
    message_id: str | None = None
    provider_message_id: str | None = None
    provider_payload: dict[str, object] = {}
    occurred_at: datetime | None = None


class UnsubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    domain: str | None = None
    channel: str = "email"
    reason: str = "unsubscribe"
    provider_payload: dict[str, object] = {}


class InboundEmailEventOut(BaseModel):
    id: str
    enrollment_id: str | None = None
    outbound_email_id: str | None = None
    event_type: InboundEmailEventType
    from_email: EmailStr | None = None
    to_email: EmailStr | None = None
    message_id: str | None = None
    provider_payload: dict[str, object] = {}
    occurred_at: datetime
    created_at: datetime


class JobAccepted(BaseModel):
    job_id: UUID
    status: str = "accepted"
