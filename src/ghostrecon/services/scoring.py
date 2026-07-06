from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    CandidateScoreOut,
    CandidateScoreRequest,
    CandidateScoreRoute,
    OriginType,
    ScoreRequest,
    ScoreResult,
)
from ghostrecon.models.db import CandidateScore, OutboxEvent, ReviewCandidate

SCORING_CONFIG_VERSION = "sprint7.v1"
SCORING_WEIGHTS = {
    "fit": 0.25,
    "relevance": 0.25,
    "recency": 0.15,
    "confidence": 0.15,
    "evidence": 0.20,
}


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


async def create_candidate_score(
    request: CandidateScoreRequest,
    *,
    idempotency_key: str,
    settings: Settings | None = None,
) -> CandidateScore:
    async with session_scope(settings) as session:
        existing = await session.scalar(
            select(CandidateScore).where(CandidateScore.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing

        preview = score_candidate_preview(request)
        component_scores = {
            "fit": preview.fit_score,
            "relevance": preview.relevance_score,
            "recency": preview.recency_score,
            "confidence": preview.confidence_score,
            "evidence": preview.evidence_score,
            "policy_blockers": preview.policy_blockers,
        }
        score = CandidateScore(
            target_type=preview.target_type,
            target_id=preview.target_id,
            origin_type=preview.origin_type.value if preview.origin_type else None,
            origin_id=preview.origin_id,
            source_definition_id=request.source_definition_id,
            source_item_ids=list(request.source_item_ids),
            config_version=preview.config_version,
            component_scores=component_scores,
            composite_score=preview.composite_score,
            route=preview.route.value,
            reasons=list(preview.reasons),
            policy_snapshot=dict(request.policy_snapshot),
            policy_snapshot_hash=preview.policy_snapshot_hash,
            idempotency_key=idempotency_key,
        )
        session.add(score)
        await session.flush()

        _enqueue_event(
            session,
            new_event(
                event_name=EventName.LEAD_SCORED,
                aggregate_type="candidate_score",
                aggregate_id=score.id,
                source_service="scoring-routing-service",
                source_definition_id=request.source_definition_id,
                source_item_ids=request.source_item_ids,
                payload=candidate_score_to_api(score),
                idempotency_key=f"lead.scored:{score.id}",
            ),
        )
        if preview.route != CandidateScoreRoute.REJECTED:
            await _request_score_review(session, request, score, preview)
        return score


def candidate_score_to_api(score: CandidateScore) -> dict[str, object]:
    components = score.component_scores or {}
    return {
        "id": score.id,
        "target_type": score.target_type,
        "target_id": score.target_id,
        "origin_type": score.origin_type,
        "origin_id": score.origin_id,
        "config_version": score.config_version,
        "fit_score": int(components.get("fit", 0)),
        "relevance_score": int(components.get("relevance", 0)),
        "recency_score": int(components.get("recency", 0)),
        "confidence_score": int(components.get("confidence", 0)),
        "evidence_score": int(components.get("evidence", 0)),
        "composite_score": score.composite_score,
        "route": score.route,
        "reasons": score.reasons or [],
        "policy_blockers": components.get("policy_blockers", []),
        "policy_snapshot_hash": score.policy_snapshot_hash,
        "created_at": score.created_at,
    }


def candidate_score_to_model(score: CandidateScore) -> CandidateScoreOut:
    return CandidateScoreOut.model_validate(candidate_score_to_api(score))


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


def _route_for_score(score: int, policy_blockers: list[str]) -> CandidateScoreRoute:
    if policy_blockers or score < 40:
        return CandidateScoreRoute.REJECTED
    if score < 70:
        return CandidateScoreRoute.NEEDS_REVIEW
    return CandidateScoreRoute.CRM_TARGET_REVIEW


async def _request_score_review(
    session: Any,
    request: CandidateScoreRequest,
    score: CandidateScore,
    preview: CandidateScoreOut,
) -> ReviewCandidate:
    reason_code = (
        "score_ready_for_crm_target_review"
        if preview.route == CandidateScoreRoute.CRM_TARGET_REVIEW
        else "score_requires_review"
    )
    idempotency_key = f"review:scoring:{score.id}:{reason_code}"
    existing = await session.scalar(
        select(ReviewCandidate).where(ReviewCandidate.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing

    review = ReviewCandidate(
        candidate_type="scoring",
        target_type=request.target_type,
        target_id=request.target_id,
        origin_type=request.origin_type.value if request.origin_type else None,
        origin_id=request.origin_id,
        source_definition_id=request.source_definition_id,
        source_item_ids=list(request.source_item_ids),
        reason_code=reason_code,
        reason="Candidate score requires analyst review before CRM target creation.",
        evidence_summary={
            "candidate_score_id": score.id,
            "composite_score": preview.composite_score,
            "route": preview.route.value,
            "reasons": preview.reasons,
        },
        policy_snapshot=dict(request.policy_snapshot),
        policy_snapshot_hash=preview.policy_snapshot_hash,
        idempotency_key=idempotency_key,
    )
    session.add(review)
    await session.flush()
    _enqueue_event(
        session,
        new_event(
            event_name=EventName.APPROVAL_REQUESTED,
            aggregate_type="review_candidate",
            aggregate_id=review.id,
            source_service="scoring-routing-service",
            source_definition_id=request.source_definition_id,
            source_item_ids=request.source_item_ids,
            payload={
                "review_candidate_id": review.id,
                "candidate_score_id": score.id,
                "candidate_type": review.candidate_type,
                "target_type": review.target_type,
                "target_id": review.target_id,
                "reason_code": review.reason_code,
            },
            idempotency_key=f"approval.requested:{review.id}",
        ),
    )
    return review


def _enqueue_event(session: Any, event: Any) -> OutboxEvent:
    payload = event.model_dump(mode="json")
    outbox_event = OutboxEvent(
        event_name=payload["event_name"],
        aggregate_type=payload["aggregate_type"],
        aggregate_id=payload["aggregate_id"],
        idempotency_key=payload["idempotency_key"],
        payload=payload,
    )
    session.add(outbox_event)
    return outbox_event


def _optional_int(value: object, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _int_or_default(value: object, default: int = 0) -> int:
    coerced = _optional_int(value, default)
    if coerced is None:
        return default
    return coerced


def _clamp(value: int) -> int:
    return min(max(value, 0), 100)
