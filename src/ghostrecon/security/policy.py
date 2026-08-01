from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .identity import AssuranceLevel, IdentityContext

POLICY_VERSION = "sprint25.v1"


class Role(StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    GOVERNANCE_REVIEWER = "governance_reviewer"
    ADMINISTRATOR = "administrator"


class Permission(StrEnum):
    SESSION_SELF_READ = "session.self.read"
    SESSION_SELF_REVOKE = "session.self.revoke"
    PROFILE_SELF_READ = "profile.self.read"
    CANONICAL_READ = "canonical.read"
    REPORTING_READ = "reporting.read"
    GOVERNANCE_READ = "governance.read"
    INTELLIGENCE_WRITE = "intelligence.write"
    ENRICHMENT_WRITE = "enrichment.write"
    SCORING_WRITE = "scoring.write"
    WATCH_WRITE = "watch.write"
    CRM_EXPORT = "crm.export"
    SEQUENCE_WRITE = "sequence.write"
    MEETING_WRITE = "meeting.write"
    ASSIGNED_WORK_WRITE = "assigned_work.write"
    GOVERNANCE_ANNOTATE = "governance.annotate"
    GOVERNANCE_DECIDE = "governance.decide"
    GOVERNANCE_OVERRIDE = "governance.override"
    SUPPRESSION_WRITE = "suppression.write"
    SECURITY_ADMIN = "security.admin"
    SECURITY_AUDIT_READ = "security.audit.read"
    METRICS_READ = "system.metrics.read"
    DOCS_READ = "system.docs.read"


BASELINE = frozenset(
    {
        Permission.SESSION_SELF_READ,
        Permission.SESSION_SELF_REVOKE,
        Permission.PROFILE_SELF_READ,
        Permission.CANONICAL_READ,
        Permission.REPORTING_READ,
    }
)

ANALYST = frozenset(
    {
        Permission.INTELLIGENCE_WRITE,
        Permission.ENRICHMENT_WRITE,
        Permission.SCORING_WRITE,
        Permission.WATCH_WRITE,
        Permission.CRM_EXPORT,
        Permission.SEQUENCE_WRITE,
        Permission.MEETING_WRITE,
        Permission.ASSIGNED_WORK_WRITE,
    }
)

GOVERNANCE = frozenset(
    {
        Permission.GOVERNANCE_READ,
        Permission.GOVERNANCE_ANNOTATE,
        Permission.GOVERNANCE_DECIDE,
        Permission.GOVERNANCE_OVERRIDE,
        Permission.SUPPRESSION_WRITE,
    }
)

ADMIN_ONLY = frozenset(
    {
        Permission.SECURITY_ADMIN,
        Permission.SECURITY_AUDIT_READ,
        Permission.METRICS_READ,
        Permission.DOCS_READ,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: BASELINE,
    Role.ANALYST: BASELINE | ANALYST,
    Role.GOVERNANCE_REVIEWER: BASELINE | GOVERNANCE,
    Role.ADMINISTRATOR: BASELINE | ANALYST | GOVERNANCE | ADMIN_ONLY,
}


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    code: str
    required_permission: Permission


def permissions_for_roles(roles: set[str] | frozenset[str]) -> frozenset[str]:
    """Return an additive union; unknown roles never receive a baseline."""

    permissions: set[str] = set()
    for raw_role in roles:
        try:
            role = Role(raw_role)
        except ValueError:
            continue
        permissions.update(permission.value for permission in ROLE_PERMISSIONS[role])
    return frozenset(permissions)


def authorize(
    identity: IdentityContext,
    permission: Permission,
    *,
    minimum_assurance: AssuranceLevel = AssuranceLevel.EMAIL_OTP,
    maximum_authentication_age_seconds: int | None = None,
    now: datetime | None = None,
) -> AuthorizationDecision:
    if permission.value not in identity.permissions:
        return AuthorizationDecision(False, "permission_denied", permission)
    if not _assurance_satisfies(identity.assurance, minimum_assurance):
        return AuthorizationDecision(False, "step_up_required", permission)
    if (
        maximum_authentication_age_seconds is not None
        and identity.authentication_age_seconds(now) > maximum_authentication_age_seconds
    ):
        return AuthorizationDecision(False, "recent_authentication_required", permission)
    return AuthorizationDecision(True, "allowed", permission)


def _assurance_satisfies(actual: AssuranceLevel, required: AssuranceLevel) -> bool:
    if required is AssuranceLevel.WORKLOAD:
        return actual is AssuranceLevel.WORKLOAD
    if actual is AssuranceLevel.WORKLOAD:
        return False
    if required is AssuranceLevel.PHISHING_RESISTANT:
        return actual is AssuranceLevel.PHISHING_RESISTANT
    return actual in {
        AssuranceLevel.EMAIL_OTP,
        AssuranceLevel.PHISHING_RESISTANT,
    }
