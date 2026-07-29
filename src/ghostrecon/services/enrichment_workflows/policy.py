from __future__ import annotations

from datetime import UTC, datetime

from ghostrecon.models.api import (
    ContactEnrichmentCreate,
)
from ghostrecon.services.search_adapters import (
    registrable_domain_from_url,
)

ENRICHMENT_SERVICE_NAME = "enrichment-service"


EMAIL_SERVICE_NAME = "email-intelligence-service"


REVIEW_SERVICE_NAME = "governance-service"


INCIDENT_CONTACT_ROLE_SCOPES = {"security", "it", "risk", "communications"}


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    resolved = registrable_domain_from_url(domain)
    if resolved:
        return resolved
    cleaned = domain.lower().strip().removeprefix("https://").removeprefix("http://")
    return cleaned.split("/", 1)[0].removeprefix("www.").strip(".") or None


def inferred_demo_domain(*values: str | None) -> str | None:
    for value in values:
        text = str(value or "").strip().lower()
        if not text:
            continue
        if "." in text and " " not in text:
            return normalize_domain(text)
        tokens = [
            token
            for token in "".join(char if char.isalnum() else " " for char in text).split()
            if token not in {"inc", "llc", "ltd", "corp", "corporation", "company", "demo"}
        ]
        if tokens:
            return f"{'-'.join(tokens[:3])}.com"
    return None


def _json_safe(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def evaluate_contact_policy(payload: ContactEnrichmentCreate) -> tuple[str, str | None]:
    if payload.breached_data_source:
        return "blocked", "breached_data_rejected"
    if payload.origin_type == "manual" and payload.candidate_payload.get("created_by"):
        return "eligible", None
    if not payload.source_definition_id or not payload.source_item_ids:
        return "blocked", "missing_source_lineage"
    if payload.origin_type == "event_participant" and payload.reuse_state != "allowed":
        return "blocked", "participant_reuse_not_allowed"
    if (
        payload.origin_type == "security_incident"
        and payload.role_scope not in INCIDENT_CONTACT_ROLE_SCOPES
    ):
        return "blocked", "incident_role_out_of_scope"
    return "eligible", None


def classify_verification_result(result: dict[str, object]) -> tuple[str, str | None]:
    status = str(result.get("status") or result.get("result") or "").lower()
    deliverability = str(result.get("deliverability") or "").lower()
    if result.get("error") or status in {"failed", "error", "timeout"}:
        return "failed", "verifier_failed"
    if _truthy(result, "catch_all", "catchall", "is_catch_all"):
        return "needs_review", "catch_all_domain"
    if _truthy(result, "ambiguous", "unknown", "risky"):
        return "needs_review", "ambiguous_verification"
    if _truthy(result, "role_based", "role_account", "disposable"):
        return "needs_review", "policy_review_required"
    if status in {"invalid", "undeliverable", "rejected"} or result.get("valid") is False:
        return "invalid", "invalid_email"
    if status in {"valid", "deliverable", "ok"} or deliverability in {"deliverable", "valid"}:
        return "verified", None
    if result.get("valid") is True:
        return "verified", None
    return "needs_review", "ambiguous_verification"


from .serializers import _truthy  # noqa: E402
