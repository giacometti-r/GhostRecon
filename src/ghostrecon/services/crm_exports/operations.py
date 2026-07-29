from __future__ import annotations

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.configuration import assert_adapter_allowed
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    CrmExportBatchOut,
    CrmExportCreateRequest,
    CrmExportRetryRequest,
)
from ghostrecon.models.db import (
    CrmExportBatch,
    CrmExportItem,
    CrmTarget,
)
from ghostrecon.services.crm_attio import (
    CrmClient,
    CrmProviderError,
)

FAILED_ITEM_STATUSES = {"failed_retryable", "failed_terminal", "skipped_policy"}


async def start_crm_export(
    request: CrmExportCreateRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
    client: CrmClient | None = None,
) -> CrmExportBatchOut:
    resolved = settings or get_settings()
    async with session_scope(resolved) as session:
        existing = await _batch_by_idempotency_key(session, idempotency_key)
        if existing is not None:
            existing_items = await _batch_items(session, existing.id)
            return crm_export_batch_to_model(existing, existing_items)

        target_ids = _unique_ordered(request.crm_target_ids)
        targets = await _load_targets(session, target_ids)
        _require_exportable_targets(target_ids, targets)

        now = utcnow()
        batch = CrmExportBatch(
            provider=request.provider,
            workspace_id=request.workspace_id,
            requested_by=actor,
            status="running",
            crm_target_ids=target_ids,
            selection_hash=selection_hash(target_ids),
            idempotency_key=idempotency_key,
            counts={"total": len(target_ids), "pending": len(target_ids)},
            reconciliation_summary={},
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(batch)
        await session.flush()

        items: list[CrmExportItem] = []
        for target in _ordered_targets(targets):
            item = await _create_item(session, batch, target, resolved)
            session.add(item)
            items.append(item)
        await session.flush()
        _enqueue_event(
            session,
            new_event(
                event_name=EventName.CRM_EXPORT_BATCH_STARTED,
                aggregate_type="crm_export_batch",
                aggregate_id=batch.id,
                source_service=CRM_SERVICE_NAME,
                payload=crm_export_batch_to_model(batch, items).model_dump(mode="json"),
                idempotency_key=f"crm_export.batch_started:{batch.id}",
            ),
        )

    return await process_crm_export_batch(batch.id, settings=resolved, client=client)


async def get_crm_export_batch(
    batch_id: str,
    *,
    settings: Settings | None = None,
) -> CrmExportBatchOut | None:
    async with session_scope(settings) as session:
        batch = await session.get(CrmExportBatch, batch_id)
        if batch is None:
            return None
        return crm_export_batch_to_model(batch, await _batch_items(session, batch.id))


async def retry_failed_crm_export_items(
    batch_id: str,
    request: CrmExportRetryRequest | None = None,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
    client: CrmClient | None = None,
) -> CrmExportBatchOut | None:
    _ = actor, idempotency_key
    resolved = settings or get_settings()
    async with session_scope(resolved) as session:
        batch = await session.get(CrmExportBatch, batch_id)
        if batch is None:
            return None
        items = await _batch_items(session, batch.id)
        item_ids = set(request.item_ids if request else [])
        retryable = [
            item
            for item in items
            if item.status == "failed_retryable" and (not item_ids or item.id in item_ids)
        ]
        if not retryable:
            return crm_export_batch_to_model(batch, items)
        for item in retryable:
            item.status = "pending"
            item.last_error = None
            item.retry_after_seconds = None
            item.updated_at = utcnow()
        if retryable:
            batch.status = "running"
            batch.completed_at = None
            batch.updated_at = utcnow()
    return await process_crm_export_batch(batch_id, settings=resolved, client=client)


async def process_crm_export_batch(
    batch_id: str,
    *,
    settings: Settings | None = None,
    client: CrmClient | None = None,
) -> CrmExportBatchOut:
    resolved = settings or get_settings()
    crm_client = client or _crm_client_for_settings(resolved)
    assert_adapter_allowed(resolved, crm_client, "crm_provider")
    async with session_scope(resolved) as session:
        batch = await session.get(CrmExportBatch, batch_id)
        if batch is None:
            raise ValueError("crm export batch not found")
        items = await _batch_items(session, batch.id)
        if batch.completed_at is not None and not any(item.status == "pending" for item in items):
            return crm_export_batch_to_model(batch, items)
        for item in items:
            if item.status != "pending":
                continue
            target = await session.get(CrmTarget, item.crm_target_id)
            item.status = "running"
            item.attempt_count += 1
            item.updated_at = utcnow()
            if target is None:
                _mark_item_failure(item, "crm target no longer exists", retryable=False)
                continue
            try:
                plan = await _plan_for_target(session, target, resolved)
                result = await crm_client.export(plan)
            except PolicySkip as exc:
                item.status = "skipped_policy"
                item.last_error = str(exc)
                item.retry_after_seconds = None
                target.export_status = "skipped_policy"
                target.updated_at = utcnow()
                _enqueue_item_failed_event(session, batch, item)
                continue
            except CrmProviderError as exc:
                _mark_item_failure(
                    item,
                    str(exc),
                    retryable=exc.retryable,
                    retry_after_seconds=exc.retry_after_seconds,
                )
                target.export_status = item.status
                target.updated_at = utcnow()
                _enqueue_item_failed_event(session, batch, item)
                continue

            item.provider_record_id = result.provider_record_id
            item.provider_list_id = result.provider_list_id
            item.provider_list_entry_id = result.provider_list_entry_id
            item.reconciliation_state = "not_required"
            item.status = "succeeded"
            item.last_error = None
            item.retry_after_seconds = None
            item.updated_at = utcnow()
            target.status = "exported"
            target.export_status = "exported"
            target.version += 1
            target.updated_at = utcnow()
            _enqueue_event(
                session,
                new_event(
                    event_name=EventName.CRM_EXPORT_ITEM_SUCCEEDED,
                    aggregate_type="crm_export_item",
                    aggregate_id=item.id,
                    source_service=CRM_SERVICE_NAME,
                    payload=crm_export_item_to_model(item).model_dump(mode="json"),
                    idempotency_key=(f"crm_export.item_succeeded:{item.id}:{item.attempt_count}"),
                ),
            )

        _complete_batch(session, batch, await _batch_items(session, batch.id))
        return crm_export_batch_to_model(batch, await _batch_items(session, batch.id))


from .clients import _crm_client_for_settings  # noqa: E402
from .common import CRM_SERVICE_NAME, selection_hash, utcnow  # noqa: E402
from .planning import PolicySkip, _plan_for_target, _unique_ordered  # noqa: E402
from .repository import (  # noqa: E402
    _batch_by_idempotency_key,
    _batch_items,
    _create_item,
    _load_targets,
    _ordered_targets,
    _require_exportable_targets,
)
from .serializers import crm_export_batch_to_model, crm_export_item_to_model  # noqa: E402
from .status import (  # noqa: E402
    _complete_batch,
    _enqueue_event,
    _enqueue_item_failed_event,
    _mark_item_failure,
)
