from __future__ import annotations

from contextvars import ContextVar

from .identity import IdentityContext

current_identity: ContextVar[IdentityContext | None] = ContextVar(
    "ghostrecon_current_identity", default=None
)
current_operation: ContextVar[str | None] = ContextVar("ghostrecon_current_operation", default=None)
