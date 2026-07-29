from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from .common import OriginType
from .incidents import WatchTargetOut


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


class ParticipantReuseState(StrEnum):
    ALLOWED = "allowed"
    UNKNOWN = "unknown"
    PROHIBITED = "prohibited"


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


class ContactDomainDiscoveryResult(BaseModel):
    contact_candidate: ContactEnrichmentOut
    query: str
    provider: str
    selected_url: str | None = None
    discovered_domain: str | None = None
    status: ContactEnrichmentStatus
    review_reason: str | None = None


class WatchTargetContactDiscoveryResult(BaseModel):
    watch_target: WatchTargetOut
    query: str
    provider: str
    degraded: bool = False
    contact_candidates: list[ContactEnrichmentOut] = []
