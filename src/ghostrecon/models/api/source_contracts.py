from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from .identity import ParticipantReuseState
from .sources import (
    ContentStoragePolicy,
    RawSourceParseStatus,
    SourceAdapterType,
    SourceHealthStatus,
    SourceKind,
    SourcePolicyState,
)


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
