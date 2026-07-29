from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
)

from .incidents import CorroborationMethod


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
