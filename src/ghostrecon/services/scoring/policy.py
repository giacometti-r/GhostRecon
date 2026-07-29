from __future__ import annotations

import hashlib
import json

from ghostrecon.models.api import (
    CandidateScoreRequest,
    OriginType,
)

SCORING_CONFIG_VERSION = "sprint7.v1"


SCORING_WEIGHTS = {
    "fit": 0.25,
    "relevance": 0.25,
    "recency": 0.15,
    "confidence": 0.15,
    "evidence": 0.20,
}


def policy_snapshot_hash(snapshot: dict[str, object]) -> str:
    payload = json.dumps(snapshot or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def policy_blockers_for_score(request: CandidateScoreRequest) -> list[str]:
    snapshot = request.policy_snapshot or {}
    blockers: list[str] = []

    if not request.source_definition_id or not request.source_item_ids:
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

    max_age = int(snapshot.get("max_evidence_age_days") or 90)
    freshness_days = _optional_int(request.evidence.get("evidence_freshness_days"))
    if snapshot.get("stale_evidence") is True or (
        freshness_days is not None and freshness_days > max_age
    ):
        blockers.append("stale_evidence")

    is_incident = request.origin_type == OriginType.SECURITY_INCIDENT
    incident_status = str(
        snapshot.get("incident_status") or request.evidence.get("incident_status") or ""
    )
    corroboration_method = str(
        snapshot.get("corroboration_method") or request.evidence.get("corroboration_method") or ""
    )
    if is_incident and incident_status != "corroborated":
        if corroboration_method not in {
            "authoritative_disclosure",
            "independent_sources",
            "analyst_decision",
        }:
            blockers.append("incident_not_corroborated")

    return blockers


from .reviews import _optional_int  # noqa: E402
