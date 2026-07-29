from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from .common import OriginType
from .reviews import ReviewDecisionAction


class CandidateScoreRoute(StrEnum):
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    CRM_TARGET_REVIEW = "crm_target_review"


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
