from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .identity import IdentityContext


async def set_security_context(
    session: AsyncSession,
    identity: IdentityContext,
    *,
    operation: str,
) -> None:
    """Install transaction-local PostgreSQL context before protected access.

    Each value is passed as a bind parameter to ``set_config``.  A caller cannot
    inject SQL through identity data, and PostgreSQL clears the values at the end
    of the current transaction before a pooled connection is reused.
    """

    values = {
        "ghostrecon.subject": identity.subject,
        "ghostrecon.identity_type": identity.identity_type.value,
        "ghostrecon.calling_service": identity.calling_service or "",
        "ghostrecon.represented_subject": identity.represented_subject,
        "ghostrecon.operation": operation,
        "ghostrecon.permissions": ",".join(sorted(identity.permissions)),
        "ghostrecon.policy_version": identity.permission_policy_version,
        "ghostrecon.governance_capability": str("governance.read" in identity.permissions).lower(),
        "ghostrecon.correlation_id": identity.correlation_id,
        "ghostrecon.context_valid": "1",
        "ghostrecon.calling_workload": identity.calling_service or identity.subject,
    }
    for name, value in values.items():
        await session.execute(
            text("SELECT set_config(:name, :value, true)"),
            {"name": name, "value": value},
        )
