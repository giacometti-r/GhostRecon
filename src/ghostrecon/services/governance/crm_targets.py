from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    CrmTargetList,
    CrmTargetOut,
    CrmTargetUpdateRequest,
)
from ghostrecon.models.db import (
    CrmTarget,
    ReviewCandidate,
    ReviewDecision,
)


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


async def update_crm_target(
    crm_target_id: str,
    request: CrmTargetUpdateRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> CrmTarget | None:
    async with session_scope(settings) as session:
        target = await session.get(CrmTarget, crm_target_id)
        if target is None:
            return None
        approval = dict(target.approval_snapshot or {})
        policy = dict(target.policy_snapshot or {})
        fields = request.model_fields_set
        if "name" in fields:
            _set_or_remove(approval, "name", request.name)
            _set_or_remove(policy, "name", request.name)
        if "company" in fields:
            _set_or_remove(approval, "company", request.company)
            _set_or_remove(policy, "company", request.company)
        if "email" in fields:
            _set_or_remove(approval, "email", request.email)
            _set_or_remove(policy, "email", request.email)
        if request.status is not None:
            target.status = request.status.value
        if request.export_status is not None:
            target.export_status = request.export_status
        approval["updated_by"] = actor
        approval["updated_at"] = datetime.now(UTC).isoformat()
        target.approval_snapshot = approval
        target.policy_snapshot = policy
        target.version += 1
        target.updated_at = datetime.now(UTC)
        _audit(
            session,
            actor,
            "crm_target.updated",
            "crm_target",
            target.id,
            idempotency_key=f"crm-target.update:{target.id}:{target.version}",
            payload=crm_target_to_api(target),
        )
        await session.flush()
        return target


def crm_target_to_api(target: CrmTarget) -> dict[str, object]:
    approval = target.approval_snapshot or {}
    policy = target.policy_snapshot or {}
    return {
        "id": target.id,
        "review_candidate_id": target.review_candidate_id,
        "review_decision_id": target.review_decision_id,
        "target_type": target.target_type,
        "target_id": target.target_id,
        "display_name": approval.get("name") or policy.get("name"),
        "company_name": approval.get("company") or policy.get("company"),
        "email": approval.get("email") or policy.get("email"),
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


def _set_or_remove(mapping: dict[str, object], key: str, value: object | None) -> None:
    if value in (None, ""):
        mapping.pop(key, None)
    else:
        mapping[key] = value


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


from .review_records import _audit, _json_safe  # noqa: E402
