from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.models.db import (
    CrmExportBatch,
    CrmExportItem,
    CrmTarget,
)


async def _batch_by_idempotency_key(session: Any, idempotency_key: str) -> CrmExportBatch | None:
    return await session.scalar(
        select(CrmExportBatch).where(CrmExportBatch.idempotency_key == idempotency_key)
    )


async def _batch_items(session: Any, batch_id: str) -> list[CrmExportItem]:
    result = await session.execute(
        select(CrmExportItem).where(CrmExportItem.batch_id == batch_id).order_by(CrmExportItem.id)
    )
    return list(result.scalars())


async def _load_targets(session: Any, target_ids: list[str]) -> dict[str, CrmTarget]:
    result = await session.execute(select(CrmTarget).where(CrmTarget.id.in_(target_ids)))
    return {target.id: target for target in result.scalars()}


def _require_exportable_targets(target_ids: list[str], targets: dict[str, CrmTarget]) -> None:
    missing = [target_id for target_id in target_ids if target_id not in targets]
    if missing:
        raise ValueError(f"crm target not found: {missing[0]}")
    for target_id in target_ids:
        target = targets[target_id]
        if target.status != EXPORTABLE_TARGET_STATUS:
            raise ValueError(f"crm target {target.id} is not pending export")
        if target.export_status not in EXPORTABLE_EXPORT_STATUSES:
            raise ValueError(f"crm target {target.id} has export status {target.export_status}")


def _ordered_targets(targets: dict[str, CrmTarget]) -> list[CrmTarget]:
    return sorted(
        targets.values(),
        key=lambda target: (_target_order(target.target_type), target.id),
    )


def _target_order(target_type: str) -> int:
    normalized = _normalize_target_type(target_type)
    if normalized in {"cyber_event", "security_incident", "company"}:
        return 0
    return 1


async def _create_item(
    session: Any,
    batch: CrmExportBatch,
    target: CrmTarget,
    settings: Settings,
) -> CrmExportItem:
    try:
        plan = await _plan_for_target(session, target, settings)
        provider_object = plan.provider_object
        stable_match_key = plan.stable_match_key
    except (PolicySkip, ValueError):
        provider_object = _provider_object_for_type(target.target_type)
        stable_match_key = f"ghostrecon:{target.target_type}:{target.target_id}"
    return _new_item(batch, target, provider_object, stable_match_key)


def _new_item(
    batch: CrmExportBatch,
    target: CrmTarget,
    provider_object: str,
    stable_match_key: str,
) -> CrmExportItem:
    now = utcnow()
    return CrmExportItem(
        batch_id=batch.id,
        crm_target_id=target.id,
        target_type=target.target_type,
        target_id=target.target_id,
        operation="upsert_record",
        dependency_item_ids=[],
        provider_object=provider_object,
        stable_match_key=stable_match_key,
        status="pending",
        attempt_count=0,
        reconciliation_state="not_required",
        created_at=now,
        updated_at=now,
    )


from .common import EXPORTABLE_EXPORT_STATUSES, EXPORTABLE_TARGET_STATUS, utcnow  # noqa: E402
from .planning import (  # noqa: E402
    PolicySkip,
    _normalize_target_type,
    _plan_for_target,
    _provider_object_for_type,
)
