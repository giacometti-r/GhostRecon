from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    BulkReviewDecisionRequest,
    CrmTargetList,
    CrmTargetOut,
    IncidentDecisionRequest,
    ReviewDecisionAction,
    ReviewDecisionOut,
    ReviewDecisionRequest,
    SuppressionCheckRequest,
    SuppressionCheckResult,
    SuppressionCreate,
    SuppressionOut,
)
from ghostrecon.models.db import (
    AuditEvent,
    CrmTarget,
    OutboxEvent,
    ReviewCandidate,
    ReviewDecision,
    SecurityIncident,
    Suppression,
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


def evaluate_suppression(request: SuppressionCheckRequest) -> SuppressionCheckResult:
    """Evaluate non-database suppression rules that must always apply."""

    if request.email:
        local_part = str(request.email).split("@", 1)[0].lower()
        if local_part in ROLE_BASED_PREFIXES:
            return SuppressionCheckResult(
                allowed=False,
                reason="Role-based address requires explicit approval before outreach",
            )

    if request.channel.lower() not in SUPPORTED_CHANNELS:
        return SuppressionCheckResult(allowed=False, reason="Unsupported outreach channel")

    return SuppressionCheckResult(allowed=True)


async def evaluate_suppression_with_store(
    request: SuppressionCheckRequest,
    *,
    settings: Settings | None = None,
) -> SuppressionCheckResult:
    baseline = evaluate_suppression(request)
    if not baseline.allowed:
        return baseline

    matches = []
    if request.email:
        matches.append(Suppression.email == str(request.email).lower())
    if request.domain:
        matches.append(Suppression.domain == request.domain.lower())
    if request.contact_id:
        matches.append(Suppression.contact_id == request.contact_id)
    if not matches:
        return baseline

    async with session_scope(settings) as session:
        suppression = await session.scalar(
            select(Suppression)
            .where(Suppression.active.is_(True))
            .where(Suppression.channel == request.channel.lower())
            .where(
                or_(
                    Suppression.expires_at.is_(None),
                    Suppression.expires_at > datetime.now(UTC),
                )
            )
            .where(or_(*matches))
            .limit(1)
        )
        if suppression is None:
            return baseline
        return SuppressionCheckResult(allowed=False, reason=suppression.reason)


async def create_suppression(
    request: SuppressionCreate,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> Suppression:
    async with session_scope(settings) as session:
        existing = await session.scalar(
            select(Suppression).where(Suppression.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing

        suppression = Suppression(
            email=str(request.email).lower() if request.email else None,
            domain=request.domain.lower() if request.domain else None,
            contact_id=request.contact_id,
            channel=request.channel.lower(),
            target_type=request.target_type,
            target_id=request.target_id,
            reason=request.reason,
            source=request.source,
            active=request.active,
            expires_at=request.expires_at,
            policy_snapshot=dict(request.policy_snapshot),
            idempotency_key=idempotency_key,
        )
        session.add(suppression)
        await session.flush()
        _audit(
            session,
            actor,
            "suppression.created",
            "suppression",
            suppression.id,
            idempotency_key=f"audit:{idempotency_key}",
            payload=suppression_to_api(suppression),
        )
        _enqueue_event(
            session,
            new_event(
                event_name=EventName.SUPPRESSION_CREATED,
                aggregate_type="suppression",
                aggregate_id=suppression.id,
                source_service="governance-service",
                payload=suppression_to_api(suppression),
                idempotency_key=f"suppression.created:{suppression.id}",
            ),
        )
        return suppression


async def approve_review_candidate(
    candidate_id: str,
    request: ReviewDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> ReviewDecision | None:
    async with session_scope(settings) as session:
        existing = await _existing_decision(session, idempotency_key)
        if existing is not None:
            return existing
        candidate = await session.get(ReviewCandidate, candidate_id)
        if candidate is None:
            return None
        return await _approve_review_candidate_in_session(
            session, candidate, request, actor=actor, idempotency_key=idempotency_key
        )


async def reject_review_candidate(
    candidate_id: str,
    request: ReviewDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> ReviewDecision | None:
    async with session_scope(settings) as session:
        existing = await _existing_decision(session, idempotency_key)
        if existing is not None:
            return existing
        candidate = await session.get(ReviewCandidate, candidate_id)
        if candidate is None:
            return None
        return await _reject_review_candidate_in_session(
            session, candidate, request, actor=actor, idempotency_key=idempotency_key
        )


async def bulk_decide_review_candidates(
    request: BulkReviewDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> list[ReviewDecision]:
    async with session_scope(settings) as session:
        candidates = list(
            (
                await session.scalars(
                    select(ReviewCandidate).where(ReviewCandidate.id.in_(request.candidate_ids))
                )
            ).all()
        )
        if len(candidates) != len(set(request.candidate_ids)):
            raise ValueError("bulk decision includes unknown review candidate")
        candidate_types = {candidate.candidate_type for candidate in candidates}
        if len(candidate_types) != 1:
            raise ValueError("bulk decision requires one candidate type")
        if any(candidate.status != "open" for candidate in candidates):
            raise ValueError("bulk decision only supports open candidates")

        policy_hashes = {current_policy_hash(candidate) for candidate in candidates}
        if len(policy_hashes) != 1:
            raise ValueError("bulk decision requires one policy snapshot hash")
        if request.policy_snapshot_hash and policy_hashes != {request.policy_snapshot_hash}:
            raise ValueError("bulk decision policy snapshot hash mismatch")

        decisions: list[ReviewDecision] = []
        for candidate in candidates:
            version = request.candidate_versions.get(candidate.id)
            if version is None:
                raise ValueError("bulk decision missing candidate version")
            decision_request = ReviewDecisionRequest(
                version=version,
                reason_code=request.reason_code,
                reason=request.reason,
                policy_snapshot_hash=request.policy_snapshot_hash,
                evidence_snapshot=request.evidence_snapshot,
            )
            child_idempotency_key = f"{idempotency_key}:{candidate.id}"
            existing = await _existing_decision(session, child_idempotency_key)
            if existing is not None:
                decisions.append(existing)
                continue
            if request.decision == ReviewDecisionAction.APPROVED:
                decisions.append(
                    await _approve_review_candidate_in_session(
                        session,
                        candidate,
                        decision_request,
                        actor=actor,
                        idempotency_key=child_idempotency_key,
                    )
                )
            else:
                decisions.append(
                    await _reject_review_candidate_in_session(
                        session,
                        candidate,
                        decision_request,
                        actor=actor,
                        idempotency_key=child_idempotency_key,
                    )
                )
        return decisions


async def list_crm_targets(
    *,
    status: str | None = None,
    target_type: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> list[CrmTarget]:
    async with session_scope(settings) as session:
        stmt = select(CrmTarget).order_by(CrmTarget.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(CrmTarget.status == status)
        if target_type:
            stmt = stmt.where(CrmTarget.target_type == target_type)
        return list((await session.scalars(stmt)).all())


async def corroborate_incident(
    incident_id: str,
    request: IncidentDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> ReviewDecision | None:
    async with session_scope(settings) as session:
        existing = await _existing_decision(session, idempotency_key)
        if existing is not None:
            return existing
        incident = await session.get(SecurityIncident, incident_id)
        if incident is None:
            return None
        if incident.version != request.version:
            raise ValueError("stale optimistic version")
        if request.method.value not in CORROBORATION_METHODS:
            raise ValueError("unsupported incident corroboration method")
        if request.method.value == "independent_sources":
            source_count = int(request.evidence_snapshot.get("independent_source_count") or 0)
            if source_count < 2:
                raise ValueError("independent-source corroboration requires at least two sources")

        incident.status = "corroborated"
        incident.corroboration_method = request.method.value
        incident.version += 1
        decision = _create_decision(
            session,
            review_candidate=None,
            target_type="security_incident",
            target_id=incident.id,
            decision="approved",
            actor=actor,
            reason_code=request.reason_code,
            reason=request.reason,
            evidence_snapshot=request.evidence_snapshot,
            policy_snapshot=request.policy_snapshot,
            idempotency_key=idempotency_key,
        )
        await session.flush()
        incident.analyst_decision_ref = decision.id
        _audit(
            session,
            actor,
            "security_incident.corroborated",
            "security_incident",
            incident.id,
            idempotency_key=f"audit:{idempotency_key}",
            payload=review_decision_to_api(decision),
        )
        _enqueue_event(
            session,
            new_event(
                event_name=EventName.SECURITY_INCIDENT_CORROBORATED,
                aggregate_type="security_incident",
                aggregate_id=incident.id,
                source_service="governance-service",
                payload={
                    "incident_id": incident.id,
                    "method": incident.corroboration_method,
                    "review_decision_id": decision.id,
                },
                idempotency_key=f"security_incident.corroborated:{decision.id}",
            ),
        )
        return decision


async def reject_incident(
    incident_id: str,
    request: IncidentDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> ReviewDecision | None:
    async with session_scope(settings) as session:
        existing = await _existing_decision(session, idempotency_key)
        if existing is not None:
            return existing
        incident = await session.get(SecurityIncident, incident_id)
        if incident is None:
            return None
        if incident.version != request.version:
            raise ValueError("stale optimistic version")

        incident.status = "rejected"
        incident.version += 1
        decision = _create_decision(
            session,
            review_candidate=None,
            target_type="security_incident",
            target_id=incident.id,
            decision="rejected",
            actor=actor,
            reason_code=request.reason_code,
            reason=request.reason,
            evidence_snapshot=request.evidence_snapshot,
            policy_snapshot=request.policy_snapshot,
            idempotency_key=idempotency_key,
        )
        await session.flush()
        _audit(
            session,
            actor,
            "security_incident.rejected",
            "security_incident",
            incident.id,
            idempotency_key=f"audit:{idempotency_key}",
            payload=review_decision_to_api(decision),
        )
        _enqueue_event(
            session,
            new_event(
                event_name=EventName.REVIEW_REJECTED,
                aggregate_type="security_incident",
                aggregate_id=incident.id,
                source_service="governance-service",
                payload=review_decision_to_api(decision),
                idempotency_key=f"review.rejected:{decision.id}",
            ),
        )
        return decision


async def revert_incident(
    incident_id: str,
    request: IncidentDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> ReviewDecision | None:
    async with session_scope(settings) as session:
        existing = await _existing_decision(session, idempotency_key)
        if existing is not None:
            return existing
        incident = await session.get(SecurityIncident, incident_id)
        if incident is None:
            return None
        if incident.version != request.version:
            raise ValueError("stale optimistic version")
        if incident.status != "corroborated":
            raise ValueError("only corroborated incidents can be reverted")

        incident.status = "candidate"
        incident.corroboration_method = "none"
        incident.version += 1
        decision = _create_decision(
            session,
            review_candidate=None,
            target_type="security_incident",
            target_id=incident.id,
            decision="rejected",
            actor=actor,
            reason_code=request.reason_code,
            reason=request.reason,
            evidence_snapshot=request.evidence_snapshot,
            policy_snapshot=request.policy_snapshot,
            idempotency_key=idempotency_key,
        )
        await session.flush()
        incident.analyst_decision_ref = decision.id
        _audit(
            session,
            actor,
            "security_incident.reverted",
            "security_incident",
            incident.id,
            idempotency_key=f"audit:{idempotency_key}",
            payload=review_decision_to_api(decision),
        )
        _enqueue_event(
            session,
            new_event(
                event_name=EventName.REVIEW_REJECTED,
                aggregate_type="security_incident",
                aggregate_id=incident.id,
                source_service="governance-service",
                payload={
                    **review_decision_to_api(decision),
                    "reverted_from": "corroborated",
                },
                idempotency_key=f"security_incident.reverted:{decision.id}",
            ),
        )
        return decision


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


def review_decision_to_api(decision: ReviewDecision) -> dict[str, object]:
    return {
        "id": decision.id,
        "review_candidate_id": decision.review_candidate_id,
        "target_type": decision.target_type,
        "target_id": decision.target_id,
        "decision": decision.decision,
        "actor": decision.actor,
        "reason_code": decision.reason_code,
        "reason": decision.reason,
        "policy_snapshot_hash": decision.policy_snapshot_hash,
        "created_at": decision.created_at,
    }


def review_decision_to_model(decision: ReviewDecision) -> ReviewDecisionOut:
    return ReviewDecisionOut.model_validate(review_decision_to_api(decision))


def crm_target_to_api(target: CrmTarget) -> dict[str, object]:
    return {
        "id": target.id,
        "review_candidate_id": target.review_candidate_id,
        "review_decision_id": target.review_decision_id,
        "target_type": target.target_type,
        "target_id": target.target_id,
        "origin_type": target.origin_type,
        "origin_id": target.origin_id,
        "source_definition_id": target.source_definition_id,
        "source_item_ids": target.source_item_ids or [],
        "status": target.status,
        "export_status": target.export_status,
        "policy_snapshot": target.policy_snapshot or {},
        "approval_snapshot": target.approval_snapshot or {},
        "version": target.version,
        "created_at": target.created_at,
        "updated_at": target.updated_at,
    }


def crm_target_to_model(target: CrmTarget) -> CrmTargetOut:
    return CrmTargetOut.model_validate(crm_target_to_api(target))


def crm_targets_to_model(targets: list[CrmTarget]) -> CrmTargetList:
    return CrmTargetList(crm_targets=[crm_target_to_model(target) for target in targets])


def suppression_to_api(suppression: Suppression) -> dict[str, object]:
    return {
        "id": suppression.id,
        "email": suppression.email,
        "domain": suppression.domain,
        "contact_id": suppression.contact_id,
        "channel": suppression.channel,
        "target_type": suppression.target_type,
        "target_id": suppression.target_id,
        "reason": suppression.reason,
        "source": suppression.source,
        "active": suppression.active,
        "expires_at": suppression.expires_at,
        "policy_snapshot": suppression.policy_snapshot or {},
        "created_at": suppression.created_at,
    }


def suppression_to_model(suppression: Suppression) -> SuppressionOut:
    return SuppressionOut.model_validate(suppression_to_api(suppression))


async def _approve_review_candidate_in_session(
    session: Any,
    candidate: ReviewCandidate,
    request: ReviewDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
) -> ReviewDecision:
    _validate_candidate_decision(candidate, request)
    blockers = review_policy_blockers(candidate)
    if blockers:
        raise ValueError("policy blockers: " + ", ".join(blockers))

    decision = _create_decision(
        session,
        review_candidate=candidate,
        target_type=candidate.target_type,
        target_id=candidate.target_id,
        decision="approved",
        actor=actor,
        reason_code=request.reason_code,
        reason=request.reason,
        evidence_snapshot=request.evidence_snapshot or candidate.evidence_summary or {},
        policy_snapshot=candidate.policy_snapshot or {},
        idempotency_key=idempotency_key,
    )
    candidate.status = "approved"
    candidate.version += 1
    await session.flush()

    _audit(
        session,
        actor,
        "review.approved",
        "review_candidate",
        candidate.id,
        idempotency_key=f"audit:{idempotency_key}",
        payload=review_decision_to_api(decision),
    )
    _enqueue_event(
        session,
        new_event(
            event_name=EventName.REVIEW_APPROVED,
            aggregate_type="review_candidate",
            aggregate_id=candidate.id,
            source_service="governance-service",
            source_definition_id=candidate.source_definition_id,
            source_item_ids=[str(item) for item in candidate.source_item_ids or []],
            payload=review_decision_to_api(decision),
            idempotency_key=f"review.approved:{decision.id}",
        ),
    )
    crm_target = _create_crm_target(session, candidate, decision)
    await session.flush()
    _enqueue_event(
        session,
        new_event(
            event_name=EventName.CRM_TARGET_CREATED,
            aggregate_type="crm_target",
            aggregate_id=crm_target.id,
            source_service="governance-service",
            source_definition_id=candidate.source_definition_id,
            source_item_ids=[str(item) for item in candidate.source_item_ids or []],
            payload=crm_target_to_api(crm_target),
            idempotency_key=f"crm_target.created:{crm_target.id}",
        ),
    )
    return decision


async def _reject_review_candidate_in_session(
    session: Any,
    candidate: ReviewCandidate,
    request: ReviewDecisionRequest,
    *,
    actor: str,
    idempotency_key: str,
) -> ReviewDecision:
    _validate_candidate_decision(candidate, request)
    decision = _create_decision(
        session,
        review_candidate=candidate,
        target_type=candidate.target_type,
        target_id=candidate.target_id,
        decision="rejected",
        actor=actor,
        reason_code=request.reason_code,
        reason=request.reason,
        evidence_snapshot=request.evidence_snapshot or candidate.evidence_summary or {},
        policy_snapshot=candidate.policy_snapshot or {},
        idempotency_key=idempotency_key,
    )
    candidate.status = "rejected"
    candidate.version += 1
    await session.flush()
    _audit(
        session,
        actor,
        "review.rejected",
        "review_candidate",
        candidate.id,
        idempotency_key=f"audit:{idempotency_key}",
        payload=review_decision_to_api(decision),
    )
    _enqueue_event(
        session,
        new_event(
            event_name=EventName.REVIEW_REJECTED,
            aggregate_type="review_candidate",
            aggregate_id=candidate.id,
            source_service="governance-service",
            source_definition_id=candidate.source_definition_id,
            source_item_ids=[str(item) for item in candidate.source_item_ids or []],
            payload=review_decision_to_api(decision),
            idempotency_key=f"review.rejected:{decision.id}",
        ),
    )
    return decision


def _validate_candidate_decision(
    candidate: ReviewCandidate, request: ReviewDecisionRequest
) -> None:
    if candidate.status != "open":
        raise ValueError("review candidate is not open")
    if candidate.version != request.version:
        raise ValueError("stale optimistic version")
    if request.policy_snapshot_hash and request.policy_snapshot_hash != current_policy_hash(
        candidate
    ):
        raise ValueError("policy snapshot hash mismatch")


def _create_decision(
    session: Any,
    *,
    review_candidate: ReviewCandidate | None,
    target_type: str,
    target_id: str,
    decision: str,
    actor: str,
    reason_code: str,
    reason: str | None,
    evidence_snapshot: dict[str, object],
    policy_snapshot: dict[str, object],
    idempotency_key: str,
) -> ReviewDecision:
    review_decision = ReviewDecision(
        review_candidate_id=review_candidate.id if review_candidate is not None else None,
        target_type=target_type,
        target_id=target_id,
        decision=decision,
        actor=actor,
        reason_code=reason_code,
        reason=reason,
        evidence_snapshot=_json_safe(evidence_snapshot),
        policy_snapshot=_json_safe(policy_snapshot),
        policy_snapshot_hash=policy_snapshot_hash(policy_snapshot),
        idempotency_key=idempotency_key,
    )
    session.add(review_decision)
    return review_decision


def _create_crm_target(
    session: Any, candidate: ReviewCandidate, decision: ReviewDecision
) -> CrmTarget:
    crm_target = CrmTarget(
        review_candidate_id=candidate.id,
        review_decision_id=decision.id,
        target_type=candidate.target_type,
        target_id=candidate.target_id,
        origin_type=candidate.origin_type,
        origin_id=candidate.origin_id,
        source_definition_id=candidate.source_definition_id,
        source_item_ids=list(candidate.source_item_ids or []),
        status="pending_export",
        export_status="not_exported",
        policy_snapshot=_json_safe(dict(candidate.policy_snapshot or {})),
        approval_snapshot={
            "review_decision_id": decision.id,
            "approved_by": decision.actor,
            "reason_code": decision.reason_code,
            "approved_at": decision.created_at.isoformat() if decision.created_at else None,
        },
        idempotency_key=f"crm-target:{decision.id}",
    )
    session.add(crm_target)
    return crm_target


async def _existing_decision(session: Any, idempotency_key: str) -> ReviewDecision | None:
    return await session.scalar(
        select(ReviewDecision).where(ReviewDecision.idempotency_key == idempotency_key)
    )


def _audit(
    session: Any,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    *,
    idempotency_key: str,
    payload: dict[str, object],
) -> None:
    session.add(
        AuditEvent(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            idempotency_key=idempotency_key,
            payload=_json_safe(payload),
        )
    )


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


def _json_safe(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
