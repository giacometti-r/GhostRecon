from __future__ import annotations

from typing import Any

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.db import (
    CrmExportBatch,
    CrmExportItem,
    OutboxEvent,
)


def _complete_batch(session: Any, batch: CrmExportBatch, items: list[CrmExportItem]) -> None:
    now = utcnow()
    counts = _counts(items)
    batch.counts = counts
    batch.reconciliation_summary = {
        "pending_reconciliation": len(
            [item for item in items if item.reconciliation_state == "pending"]
        )
    }
    batch.status = _batch_status(items)
    batch.completed_at = now
    batch.updated_at = now
    _enqueue_event(
        session,
        new_event(
            event_name=EventName.CRM_EXPORT_BATCH_COMPLETED,
            aggregate_type="crm_export_batch",
            aggregate_id=batch.id,
            source_service=CRM_SERVICE_NAME,
            payload=crm_export_batch_to_model(batch, items).model_dump(mode="json"),
            idempotency_key=(
                f"crm_export.batch_completed:{batch.id}:{sum(item.attempt_count for item in items)}"
            ),
        ),
    )


def _counts(items: list[CrmExportItem]) -> dict[str, object]:
    counts: dict[str, object] = {"total": len(items)}
    for item in items:
        counts[item.status] = int(counts.get(item.status, 0)) + 1
    return counts


def _batch_status(items: list[CrmExportItem]) -> str:
    if not items:
        return "failed"
    statuses = {item.status for item in items}
    if statuses <= SUCCESS_ITEM_STATUSES:
        return "succeeded"
    if statuses <= FAILED_ITEM_STATUSES:
        return "failed"
    return "partial"


def _mark_item_failure(
    item: CrmExportItem,
    message: str,
    *,
    retryable: bool,
    retry_after_seconds: int | None = None,
) -> None:
    item.status = "failed_retryable" if retryable else "failed_terminal"
    item.last_error = message
    item.retry_after_seconds = retry_after_seconds
    item.updated_at = utcnow()


def _enqueue_item_failed_event(
    session: Any,
    batch: CrmExportBatch,
    item: CrmExportItem,
) -> None:
    _ = batch
    _enqueue_event(
        session,
        new_event(
            event_name=EventName.CRM_EXPORT_ITEM_FAILED,
            aggregate_type="crm_export_item",
            aggregate_id=item.id,
            source_service=CRM_SERVICE_NAME,
            payload=crm_export_item_to_model(item).model_dump(mode="json"),
            idempotency_key=f"crm_export.item_failed:{item.id}:{item.attempt_count}",
        ),
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


from .common import CRM_SERVICE_NAME, SUCCESS_ITEM_STATUSES, utcnow  # noqa: E402
from .operations import FAILED_ITEM_STATUSES  # noqa: E402
from .serializers import crm_export_batch_to_model, crm_export_item_to_model  # noqa: E402
