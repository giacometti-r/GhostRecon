from fastapi import Depends, Header, HTTPException

from ghostrecon.models.api import (
    DashboardRole,
    ReportingOperatorContext,
)


def reporting_operator_context(
    actor: str = Header(default="system", alias="X-Actor"),
    operator_role: str = Header(default=DashboardRole.VIEWER.value, alias="X-Operator-Role"),
) -> ReportingOperatorContext:
    try:
        role = DashboardRole(operator_role)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="unsupported operator role") from exc
    return ReportingOperatorContext(actor=actor, role=role)


REPORTING_OPERATOR_CONTEXT = Depends(reporting_operator_context)
