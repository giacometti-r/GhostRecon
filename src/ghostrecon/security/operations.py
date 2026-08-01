from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from .identity import AssuranceLevel
from .policy import Permission


class AuthenticationMode(StrEnum):
    PUBLIC = "public"
    HUMAN = "human"
    SERVICE = "service"
    HUMAN_OR_SERVICE = "human_or_service"
    SERVICE_WITH_OBO = "service_with_obo"


class Exposure(StrEnum):
    PUBLIC = "public"
    GATEWAY = "gateway"
    CLUSTER = "cluster"
    DISABLED = "disabled"


class RateClass(StrEnum):
    EXEMPT = "exempt"
    AUTH = "auth"
    SESSION = "session"
    READ = "read"
    EXPENSIVE_READ = "expensive_read"
    MUTATION = "mutation"
    BULK_EXPORT = "bulk_export"
    OWNER = "owner"


@dataclass(frozen=True, slots=True)
class OperationPolicy:
    operation_id: str
    owner: str
    permission: Permission | None
    authentication: AuthenticationMode
    assurance: AssuranceLevel | None
    rls: bool
    audit: bool
    csrf: bool
    rate_class: RateClass
    maximum_body_bytes: int
    exposure: Exposure
    allowed_callers: frozenset[str] = frozenset()

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in ("permission", "authentication", "assurance", "rate_class", "exposure"):
            item = value[key]
            value[key] = item.value if item is not None else None
        value["allowed_callers"] = sorted(value["allowed_callers"])
        return value


DEFAULT_BODY_BYTES = 1024 * 1024

SECURITY_OPERATIONS = (
    OperationPolicy(
        "auth.login",
        "gateway-service",
        None,
        AuthenticationMode.PUBLIC,
        None,
        False,
        True,
        False,
        RateClass.AUTH,
        0,
        Exposure.GATEWAY,
    ),
    OperationPolicy(
        "auth.callback",
        "gateway-service",
        None,
        AuthenticationMode.PUBLIC,
        None,
        False,
        True,
        False,
        RateClass.AUTH,
        0,
        Exposure.GATEWAY,
    ),
    OperationPolicy(
        "auth.session.read",
        "gateway-service",
        Permission.SESSION_SELF_READ,
        AuthenticationMode.HUMAN,
        AssuranceLevel.EMAIL_OTP,
        True,
        False,
        False,
        RateClass.SESSION,
        0,
        Exposure.GATEWAY,
    ),
    OperationPolicy(
        "auth.logout",
        "gateway-service",
        Permission.SESSION_SELF_REVOKE,
        AuthenticationMode.HUMAN,
        AssuranceLevel.EMAIL_OTP,
        True,
        True,
        True,
        RateClass.SESSION,
        0,
        Exposure.GATEWAY,
    ),
    OperationPolicy(
        "security.users.manage",
        "gateway-service",
        Permission.SECURITY_ADMIN,
        AuthenticationMode.HUMAN,
        AssuranceLevel.PHISHING_RESISTANT,
        True,
        True,
        True,
        RateClass.MUTATION,
        64 * 1024,
        Exposure.GATEWAY,
    ),
    OperationPolicy(
        "security.audit.read",
        "gateway-service",
        Permission.SECURITY_AUDIT_READ,
        AuthenticationMode.HUMAN,
        AssuranceLevel.PHISHING_RESISTANT,
        True,
        True,
        False,
        RateClass.EXPENSIVE_READ,
        0,
        Exposure.GATEWAY,
    ),
    OperationPolicy(
        "system.health.read",
        "all",
        None,
        AuthenticationMode.PUBLIC,
        None,
        False,
        False,
        False,
        RateClass.EXEMPT,
        0,
        Exposure.PUBLIC,
    ),
    OperationPolicy(
        "system.readiness.read",
        "all",
        None,
        AuthenticationMode.SERVICE,
        AssuranceLevel.WORKLOAD,
        False,
        False,
        False,
        RateClass.OWNER,
        0,
        Exposure.CLUSTER,
        frozenset({"kubernetes-probe"}),
    ),
    OperationPolicy(
        "system.metrics.read",
        "all",
        Permission.METRICS_READ,
        AuthenticationMode.SERVICE,
        AssuranceLevel.WORKLOAD,
        False,
        True,
        False,
        RateClass.OWNER,
        0,
        Exposure.CLUSTER,
        frozenset({"metrics-collector"}),
    ),
    OperationPolicy(
        "system.docs.read",
        "all",
        Permission.DOCS_READ,
        AuthenticationMode.HUMAN,
        AssuranceLevel.PHISHING_RESISTANT,
        False,
        True,
        False,
        RateClass.READ,
        0,
        Exposure.DISABLED,
    ),
)


class OperationRegistry:
    def __init__(self, policies: tuple[OperationPolicy, ...] = SECURITY_OPERATIONS) -> None:
        self._policies: dict[str, OperationPolicy] = {}
        for policy in policies:
            if policy.operation_id in self._policies:
                raise ValueError(f"duplicate operation id: {policy.operation_id}")
            self._policies[policy.operation_id] = policy

    def require(self, operation_id: str) -> OperationPolicy:
        try:
            return self._policies[operation_id]
        except KeyError as exc:
            raise KeyError(f"unclassified operation: {operation_id}") from exc

    def matrix(self) -> list[dict[str, Any]]:
        return [
            self._policies[key].as_dict()
            for key in sorted(self._policies)
        ]


OPERATIONS = OperationRegistry()
