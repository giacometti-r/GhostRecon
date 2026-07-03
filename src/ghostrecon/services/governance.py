from ghostrecon.models.api import SuppressionCheckRequest, SuppressionCheckResult

ROLE_BASED_PREFIXES = {
    "admin",
    "abuse",
    "billing",
    "contact",
    "info",
    "privacy",
    "sales",
    "support",
}


def evaluate_suppression(request: SuppressionCheckRequest) -> SuppressionCheckResult:
    """Evaluate non-database suppression rules that must always apply."""

    if request.email:
        local_part = request.email.split("@", 1)[0].lower()
        if local_part in ROLE_BASED_PREFIXES:
            return SuppressionCheckResult(
                allowed=False,
                reason="Role-based address requires explicit approval before outreach",
            )

    if request.channel.lower() not in {"email", "task", "call", "linkedin"}:
        return SuppressionCheckResult(allowed=False, reason="Unsupported outreach channel")

    return SuppressionCheckResult(allowed=True)
