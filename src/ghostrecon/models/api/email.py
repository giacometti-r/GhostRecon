from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)

from .common import OriginType
from .identity import ContactEnrichmentOut, ContactRoleScope, EmailVerificationStatus


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


class EventParticipantEnrichRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str | None = Field(default=None, max_length=255)
    role_scope: ContactRoleScope = ContactRoleScope.UNKNOWN


class EventParticipantEnrichResult(BaseModel):
    contact_candidate: ContactEnrichmentOut
    email_candidates: list[EmailCandidateRecordOut] = []
    verified_email: EmailStr | None = None
    review_reason: str | None = None
