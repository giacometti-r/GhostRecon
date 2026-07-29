from __future__ import annotations

from ghostrecon.models.db import (
    ReviewCandidate,
)
from ghostrecon.services.scoring import policy_snapshot_hash

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


SUPPORTED_CHANNELS = {"email", "task", "call", "linkedin"}


CORROBORATION_METHODS = {
    "authoritative_disclosure",
    "independent_sources",
    "analyst_decision",
}


def current_policy_hash(candidate: ReviewCandidate) -> str:
    return candidate.policy_snapshot_hash or policy_snapshot_hash(candidate.policy_snapshot or {})


def review_policy_blockers(candidate: ReviewCandidate) -> list[str]:
    snapshot = candidate.policy_snapshot or {}
    blockers: list[str] = []

    if not candidate.source_definition_id or not candidate.source_item_ids:
        blockers.append("missing_source_lineage")

    reuse_state = str(snapshot.get("participant_reuse_state") or "").lower()
    if reuse_state in {"unknown", "prohibited"}:
        blockers.append(f"participant_reuse_{reuse_state}")

    if snapshot.get("suppressed") is True or snapshot.get("suppression_allowed") is False:
        blockers.append("suppression_active")

    if snapshot.get("lawful_basis_required", True) and not snapshot.get("lawful_basis"):
        blockers.append("missing_lawful_basis")

    retention_state = str(snapshot.get("retention_state") or "").lower()
    if retention_state in {"missing", "expired"}:
        blockers.append(f"retention_{retention_state}")

    if snapshot.get("stale_evidence") is True:
        blockers.append("stale_evidence")

    if candidate.origin_type == "security_incident":
        incident_status = str(snapshot.get("incident_status") or "").lower()
        corroboration_method = str(snapshot.get("corroboration_method") or "").lower()
        if incident_status != "corroborated" and corroboration_method not in CORROBORATION_METHODS:
            blockers.append("incident_not_corroborated")

    return blockers
