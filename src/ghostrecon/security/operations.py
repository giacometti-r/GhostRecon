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
    maximum_authentication_age_seconds: int | None = None
    resource: str = "application"
    test_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in ("permission", "authentication", "assurance", "rate_class", "exposure"):
            item = value[key]
            value[key] = item.value if item is not None else None
        value["allowed_callers"] = sorted(value["allowed_callers"])
        value["test_ids"] = list(value["test_ids"])
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

EXTRA_SECURITY_OPERATIONS = tuple(
    OperationPolicy(
        operation_id=operation_id,
        owner="gateway-service",
        permission=permission,
        authentication=authentication,
        assurance=assurance,
        rls=permission is not None,
        audit=audit,
        csrf=csrf,
        rate_class=rate_class,
        maximum_body_bytes=64 * 1024 if csrf else 0,
        exposure=Exposure.GATEWAY,
        maximum_authentication_age_seconds=900
        if assurance is AssuranceLevel.PHISHING_RESISTANT
        else None,
        resource="security",
        test_ids=(f"route:{operation_id}",),
    )
    for operation_id, permission, authentication, assurance, csrf, audit, rate_class in (
        (
            "auth.claims.refresh",
            Permission.SESSION_SELF_READ,
            AuthenticationMode.HUMAN,
            AssuranceLevel.EMAIL_OTP,
            False,
            True,
            RateClass.AUTH,
        ),
        (
            "auth.step_up",
            Permission.SESSION_SELF_READ,
            AuthenticationMode.HUMAN,
            AssuranceLevel.EMAIL_OTP,
            False,
            True,
            RateClass.AUTH,
        ),
        (
            "auth.provider_logout.callback",
            None,
            AuthenticationMode.PUBLIC,
            None,
            False,
            True,
            RateClass.AUTH,
        ),
        (
            "auth.sessions.list",
            Permission.SESSION_SELF_READ,
            AuthenticationMode.HUMAN,
            AssuranceLevel.EMAIL_OTP,
            False,
            False,
            RateClass.SESSION,
        ),
        (
            "auth.sessions.revoke",
            Permission.SESSION_SELF_REVOKE,
            AuthenticationMode.HUMAN,
            AssuranceLevel.EMAIL_OTP,
            True,
            True,
            RateClass.SESSION,
        ),
        (
            "auth.logout_all",
            Permission.SESSION_SELF_REVOKE,
            AuthenticationMode.HUMAN,
            AssuranceLevel.EMAIL_OTP,
            True,
            True,
            RateClass.SESSION,
        ),
        (
            "auth.bootstrap_proof",
            Permission.SECURITY_ADMIN,
            AuthenticationMode.HUMAN,
            AssuranceLevel.PHISHING_RESISTANT,
            True,
            True,
            RateClass.MUTATION,
        ),
        (
            "security.users.list",
            Permission.SECURITY_ADMIN,
            AuthenticationMode.HUMAN,
            AssuranceLevel.PHISHING_RESISTANT,
            False,
            True,
            RateClass.READ,
        ),
        (
            "security.users.read",
            Permission.SECURITY_ADMIN,
            AuthenticationMode.HUMAN,
            AssuranceLevel.PHISHING_RESISTANT,
            False,
            True,
            RateClass.READ,
        ),
        (
            "security.users.sessions.list",
            Permission.SECURITY_ADMIN,
            AuthenticationMode.HUMAN,
            AssuranceLevel.PHISHING_RESISTANT,
            False,
            True,
            RateClass.READ,
        ),
        (
            "security.users.sessions.revoke",
            Permission.SECURITY_ADMIN,
            AuthenticationMode.HUMAN,
            AssuranceLevel.PHISHING_RESISTANT,
            True,
            True,
            RateClass.MUTATION,
        ),
        (
            "security.emergency_grants.proof",
            Permission.SECURITY_ADMIN,
            AuthenticationMode.HUMAN,
            AssuranceLevel.PHISHING_RESISTANT,
            True,
            True,
            RateClass.MUTATION,
        ),
    )
)


class OperationRegistry:
    def __init__(self, policies: tuple[OperationPolicy, ...] | None = None) -> None:
        self._policies: dict[str, OperationPolicy] = {}
        policies = (
            policies if policies is not None else SECURITY_OPERATIONS + EXTRA_SECURITY_OPERATIONS
        )
        for policy in policies:
            if policy.operation_id in self._policies:
                raise ValueError(f"duplicate operation id: {policy.operation_id}")
            self._policies[policy.operation_id] = policy

    def require(self, operation_id: str) -> OperationPolicy:
        try:
            return self._policies[operation_id]
        except KeyError as exc:
            raise KeyError(f"unclassified operation: {operation_id}") from exc

    def register(self, policy: OperationPolicy) -> None:
        if policy.operation_id in self._policies:
            raise ValueError(f"duplicate operation id: {policy.operation_id}")
        self._policies[policy.operation_id] = policy

    def ensure(self, policy: OperationPolicy) -> None:
        existing = self._policies.get(policy.operation_id)
        if existing is None:
            self._policies[policy.operation_id] = policy
        elif existing != policy:
            raise ValueError(f"conflicting classification for operation id: {policy.operation_id}")

    def matrix(self) -> list[dict[str, Any]]:
        return [self._policies[key].as_dict() for key in sorted(self._policies)]


OPERATIONS = OperationRegistry()


_READ_NAMES = frozenset(
    {
        "intelligence_events",
        "intelligence_event_detail",
        "intelligence_event_participants",
        "intelligence_participants",
        "intelligence_incidents",
        "intelligence_incident_detail",
        "intelligence_watch_targets",
        "intelligence_watch_target_detail",
        "enrichment_entity_resolutions",
        "enrichment_contact_candidates",
        "sequence_activity_list",
        "sequence_activity_detail",
        "sequence_list",
        "sequence_detail",
        "sequence_crm_prospect_list",
        "sequence_enrollment_list",
        "sequence_enrollment_detail",
        "meeting_list",
        "meeting_detail",
        "crm_export_detail",
        "source_health",
        "service_map",
    }
)


def classify_domain_operation(
    name: str, path: str, methods: set[str] | frozenset[str]
) -> OperationPolicy:
    """Return the single checked classification for every domain route."""

    method = sorted(methods - {"HEAD", "OPTIONS"})[0]
    if name.startswith("reporting_") or name == "kpi_catalog":
        permission, owner = Permission.REPORTING_READ, "reporting-service"
    elif name.startswith(("review_", "governance_", "suppression_")):
        owner = "governance-service"
        if method == "GET":
            permission = Permission.GOVERNANCE_READ
        elif name.endswith(("approve", "reject", "bulk_decision")) or name.startswith(
            "governance_"
        ):
            permission = Permission.GOVERNANCE_DECIDE
        else:
            permission = Permission.GOVERNANCE_ANNOTATE
    elif name.startswith("sequence_"):
        owner = "sequencing-service"
        permission = Permission.CANONICAL_READ if name in _READ_NAMES else Permission.SEQUENCE_WRITE
    elif name.startswith(("meeting_", "calendar_", "prep_packet")):
        owner = "meeting-handoff-service"
        permission = Permission.CANONICAL_READ if name in _READ_NAMES else Permission.MEETING_WRITE
    elif name.startswith("crm_"):
        owner = "crm-service"
        permission = Permission.CANONICAL_READ if name in _READ_NAMES else Permission.CRM_EXPORT
    elif name.startswith(("enrichment_", "email_")):
        owner = "email-intelligence-service" if name.startswith("email_") else "enrichment-service"
        permission = (
            Permission.CANONICAL_READ if name in _READ_NAMES else Permission.ENRICHMENT_WRITE
        )
    elif name in {"candidate_score", "lead_score"}:
        owner, permission = "scoring-routing-service", Permission.SCORING_WRITE
    elif "incident" in name or "watch_target" in name:
        owner = "incident-intelligence-service"
        permission = (
            Permission.CANONICAL_READ if name in _READ_NAMES else Permission.INTELLIGENCE_WRITE
        )
    else:
        owner = "event-intelligence-service"
        permission = (
            Permission.CANONICAL_READ if name in _READ_NAMES else Permission.INTELLIGENCE_WRITE
        )
    privileged = permission in {
        Permission.GOVERNANCE_DECIDE,
        Permission.GOVERNANCE_OVERRIDE,
        Permission.SECURITY_ADMIN,
    }
    return OperationPolicy(
        operation_id=f"domain.{name}",
        owner=owner,
        permission=permission,
        authentication=AuthenticationMode.HUMAN_OR_SERVICE,
        assurance=AssuranceLevel.PHISHING_RESISTANT if privileged else AssuranceLevel.EMAIL_OTP,
        rls=True,
        audit=method != "GET" or privileged,
        csrf=method not in {"GET", "HEAD", "OPTIONS"},
        rate_class=RateClass.READ if method == "GET" else RateClass.MUTATION,
        maximum_body_bytes=0 if method == "GET" else DEFAULT_BODY_BYTES,
        exposure=Exposure.GATEWAY,
        allowed_callers=frozenset({"gateway-service", "console-service"}),
        maximum_authentication_age_seconds=900 if privileged else None,
        resource=path,
        test_ids=(f"contract:{method}:{path}",),
    )


def operation_id_for_request(method: str, concrete_path: str) -> str:
    """Resolve a concrete request to exactly one classified route template."""

    import re

    matches: list[str] = []
    for policy in OPERATIONS._policies.values():
        if not policy.operation_id.startswith("domain."):
            continue
        test_id = policy.test_ids[0] if policy.test_ids else ""
        if not test_id.startswith(f"contract:{method.upper()}:"):
            continue
        template = policy.resource
        pattern = re.sub(r"\{[^/]+\}", r"[^/]+", template)
        if re.fullmatch(pattern, concrete_path):
            matches.append(policy.operation_id)
    if len(matches) != 1:
        raise KeyError(f"request has no unique operation policy: {method} {concrete_path}")
    return matches[0]
