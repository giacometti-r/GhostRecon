from __future__ import annotations

from ghostrecon.models.api import (
    CandidateScoreOut,
    CandidateScoreRequest,
    CandidateScoreRoute,
    ScoreRequest,
    ScoreResult,
)


def score_lead(request: ScoreRequest) -> ScoreResult:
    account = request.account
    signals = request.signals

    reasons: list[str] = []
    fit_score = 0
    intent_score = 0

    if account.get("named_account_flag"):
        fit_score += 30
        reasons.append("Named account")
    if account.get("employee_count") and int(account["employee_count"]) >= 250:
        fit_score += 20
        reasons.append("Employee count matches target segment")
    if account.get("security_stack") or account.get("tech_stack"):
        fit_score += 20
        reasons.append("Technographic context available")
    if account.get("industry"):
        fit_score += 20
        reasons.append("Industry present")

    for signal in signals:
        strength = int(signal.get("signal_strength", 0))
        intent_score += min(max(strength, 0), 35)
        if signal.get("signal_type") in {"kev", "cve", "intent_surge"}:
            reasons.append(f"Relevant signal: {signal.get('signal_type')}")

    fit_score = min(fit_score, 100)
    intent_score = min(intent_score, 100)
    composite_score = round((fit_score * 0.55) + (intent_score * 0.45))
    threshold_met = composite_score >= 60

    if not threshold_met:
        reasons.append("Composite score below routing threshold")

    return ScoreResult(
        fit_score=fit_score,
        intent_score=intent_score,
        composite_score=composite_score,
        threshold_met=threshold_met,
        reasons=reasons,
    )


def score_candidate_preview(request: CandidateScoreRequest) -> CandidateScoreOut:
    component_scores, reasons = _component_scores(request)
    policy_blockers = policy_blockers_for_score(request)
    if policy_blockers:
        reasons.extend(f"Policy blocker: {blocker}" for blocker in policy_blockers)

    composite = round(
        (component_scores["fit"] * SCORING_WEIGHTS["fit"])
        + (component_scores["relevance"] * SCORING_WEIGHTS["relevance"])
        + (component_scores["recency"] * SCORING_WEIGHTS["recency"])
        + (component_scores["confidence"] * SCORING_WEIGHTS["confidence"])
        + (component_scores["evidence"] * SCORING_WEIGHTS["evidence"])
    )
    route = _route_for_score(composite, policy_blockers)

    if route == CandidateScoreRoute.REJECTED and not policy_blockers:
        reasons.append("Composite score below review threshold")
    elif route == CandidateScoreRoute.NEEDS_REVIEW:
        reasons.append("Composite score requires analyst review")
    elif route == CandidateScoreRoute.CRM_TARGET_REVIEW:
        reasons.append("Composite score is ready for CRM-target review")

    return CandidateScoreOut(
        target_type=request.target_type,
        target_id=request.target_id,
        origin_type=request.origin_type,
        origin_id=request.origin_id,
        config_version=SCORING_CONFIG_VERSION,
        fit_score=component_scores["fit"],
        relevance_score=component_scores["relevance"],
        recency_score=component_scores["recency"],
        confidence_score=component_scores["confidence"],
        evidence_score=component_scores["evidence"],
        composite_score=composite,
        route=route,
        reasons=reasons,
        policy_blockers=policy_blockers,
        policy_snapshot_hash=policy_snapshot_hash(request.policy_snapshot),
    )


from .components import _component_scores  # noqa: E402
from .policy import (  # noqa: E402
    SCORING_CONFIG_VERSION,
    SCORING_WEIGHTS,
    policy_blockers_for_score,
    policy_snapshot_hash,
)
from .reviews import _route_for_score  # noqa: E402
