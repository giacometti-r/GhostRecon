from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from .common import OriginType
from .reviews import ReviewCandidateStatus, ReviewCandidateType


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


class ReviewCandidateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
