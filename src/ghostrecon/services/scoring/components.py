from __future__ import annotations

from ghostrecon.models.api import (
    CandidateScoreRequest,
    OriginType,
)


def _component_scores(request: CandidateScoreRequest) -> tuple[dict[str, int], list[str]]:
    reasons: list[str] = []
    account = request.account or {}
    contact = request.contact or {}
    evidence = request.evidence or {}
    signals = request.signals or []

    fit = 0
    if account.get("named_account_flag"):
        fit += 30
        reasons.append("Named account")
    if _int_or_default(account.get("employee_count")) >= 250:
        fit += 20
        reasons.append("Employee count matches target segment")
    if account.get("security_stack") or account.get("tech_stack"):
        fit += 20
        reasons.append("Technographic context available")
    if account.get("industry"):
        fit += 15
        reasons.append("Industry context available")
    if contact.get("role_scope") in {"security", "it", "risk", "communications"}:
        fit += 15
        reasons.append("Contact role is in permitted business scope")

    relevance = 0
    if request.origin_type == OriginType.SECURITY_INCIDENT:
        relevance += 35
        reasons.append("Security incident origin")
    elif request.origin_type in {OriginType.CYBER_EVENT, OriginType.EVENT_PARTICIPANT}:
        relevance += 25
        reasons.append("Cyber event origin")
    if evidence.get("attack_vector") or evidence.get("incident_type"):
        relevance += 25
        reasons.append("Incident context is present")
    for signal in signals:
        strength = _int_or_default(signal.get("signal_strength"))
        relevance += min(max(strength, 0), 20)
        if signal.get("signal_type"):
            reasons.append(f"Relevant signal: {signal.get('signal_type')}")

    confidence = max(
        [
            _int_or_default(evidence.get("confidence")),
            _int_or_default(account.get("source_confidence")),
            _int_or_default(contact.get("source_confidence")),
        ]
    )
    if confidence >= 70:
        reasons.append("Source confidence is strong")
    elif confidence == 0:
        reasons.append("Source confidence missing")

    evidence_score = 0
    independent_sources = _int_or_default(evidence.get("independent_source_count"))
    if evidence.get("authoritative"):
        evidence_score += 60
        reasons.append("Authoritative evidence")
    if independent_sources >= 2:
        evidence_score += 50
        reasons.append("Independent evidence threshold met")
    elif independent_sources == 1:
        evidence_score += 25
        reasons.append("Single independent evidence family")
    if evidence.get("evidence_ids") or request.source_item_ids:
        evidence_score += 20
        reasons.append("Evidence lineage is present")

    freshness_days = _optional_int(evidence.get("evidence_freshness_days"))
    if freshness_days is None:
        recency = 30
        reasons.append("Evidence recency missing")
    elif freshness_days <= 7:
        recency = 100
        reasons.append("Evidence is very recent")
    elif freshness_days <= 30:
        recency = 75
    elif freshness_days <= 90:
        recency = 45
    else:
        recency = 10
        reasons.append("Evidence is stale")

    return (
        {
            "fit": _clamp(fit),
            "relevance": _clamp(relevance),
            "recency": _clamp(recency),
            "confidence": _clamp(confidence),
            "evidence": _clamp(evidence_score),
        },
        reasons,
    )


from .reviews import _clamp, _int_or_default, _optional_int  # noqa: E402
