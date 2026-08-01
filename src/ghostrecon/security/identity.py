from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID


class IdentityType(StrEnum):
    HUMAN = "human"
    SERVICE = "service"
    WORKER = "worker"


class AssuranceLevel(StrEnum):
    EMAIL_OTP = "aal1"
    PHISHING_RESISTANT = "aal2_phishing_resistant"
    WORKLOAD = "workload"


@dataclass(frozen=True, slots=True)
class IdentityContext:
    """The only identity contract accepted by business and data-access code.

    Provider claims and credentials are deliberately absent.  All collections are
    copied to immutable values so middleware cannot change authorization state
    after a handler or repository receives the context.
    """

    identity_type: IdentityType
    subject: str
    actor_label: str
    issuer: str
    audience: tuple[str, ...]
    roles: frozenset[str]
    permissions: frozenset[str]
    calling_service: str | None
    on_behalf_of_subject: str | None
    authentication_method: str
    authenticated_at: datetime
    assurance: AssuranceLevel
    session_id: UUID | None
    correlation_id: str
    request_id: str
    claim_mapping_version: str
    permission_policy_version: str
    environment: str
    workspace_id: str = "default"
    email_verified: bool | None = None
    attributes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError("identity subject is required")
        if not self.issuer.strip():
            raise ValueError("identity issuer is required")
        if not self.audience:
            raise ValueError("identity audience is required")
        if self.authenticated_at.tzinfo is None:
            raise ValueError("authenticated_at must be timezone-aware")
        object.__setattr__(self, "audience", tuple(self.audience))
        object.__setattr__(self, "roles", frozenset(self.roles))
        object.__setattr__(self, "permissions", frozenset(self.permissions))
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))

    @property
    def represented_subject(self) -> str:
        return self.on_behalf_of_subject or self.subject

    def authentication_age_seconds(self, now: datetime | None = None) -> float:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return max(0.0, (current - self.authenticated_at).total_seconds())
