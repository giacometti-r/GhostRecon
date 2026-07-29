from __future__ import annotations

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    IncidentDecisionRequest,
)
from ghostrecon.models.db import (
    ReviewDecision,
    SecurityIncident,
)


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


from .policy import CORROBORATION_METHODS  # noqa: E402  # noqa: E402
from .review_records import (  # noqa: E402
    _audit,
    _create_decision,
    _enqueue_event,
    review_decision_to_api,
)
from .review_repository import _existing_decision  # noqa: E402
