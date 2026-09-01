from fastapi import Depends, Request

from ghostrecon.models.api import DashboardRole, ReportingOperatorContext
from ghostrecon.security.identity import IdentityContext
from ghostrecon.security.policy import Permission


def verified_identity(request: Request) -> IdentityContext:
    return request.state.identity


VERIFIED_IDENTITY = Depends(verified_identity)


def verified_actor(identity: IdentityContext = VERIFIED_IDENTITY) -> str:
    return identity.actor_label


def reporting_operator_context(
    identity: IdentityContext = VERIFIED_IDENTITY,
) -> ReportingOperatorContext:
    permissions = identity.permissions
    if Permission.SECURITY_ADMIN.value in permissions:
        role = DashboardRole.ADMINISTRATOR
    elif Permission.GOVERNANCE_DECIDE.value in permissions:
        role = DashboardRole.GOVERNANCE_REVIEWER
    elif Permission.INTELLIGENCE_WRITE.value in permissions:
        role = DashboardRole.ANALYST
    else:
        role = DashboardRole.VIEWER
    return ReportingOperatorContext(actor=identity.actor_label, role=role)


VERIFIED_ACTOR = Depends(verified_actor)
REPORTING_OPERATOR_CONTEXT = Depends(reporting_operator_context)
