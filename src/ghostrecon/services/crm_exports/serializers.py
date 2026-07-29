from __future__ import annotations

from ghostrecon.models.api import (
    CrmExportBatchOut,
    CrmExportItemOut,
)
from ghostrecon.models.db import (
    CrmExportBatch,
    CrmExportItem,
)


def crm_export_item_to_model(item: CrmExportItem) -> CrmExportItemOut:
    return CrmExportItemOut(
        id=item.id,
        batch_id=item.batch_id,
        crm_target_id=item.crm_target_id,
        target_type=item.target_type,
        target_id=item.target_id,
        operation=item.operation,
        dependency_item_ids=item.dependency_item_ids or [],
        provider_object=item.provider_object,
        provider_record_id=item.provider_record_id,
        provider_list_id=item.provider_list_id,
        provider_list_entry_id=item.provider_list_entry_id,
        stable_match_key=item.stable_match_key,
        status=item.status,
        attempt_count=item.attempt_count,
        last_error=item.last_error,
        retry_after_seconds=item.retry_after_seconds,
        reconciliation_state=item.reconciliation_state,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def crm_export_batch_to_model(
    batch: CrmExportBatch,
    items: list[CrmExportItem],
) -> CrmExportBatchOut:
    return CrmExportBatchOut(
        id=batch.id,
        provider=batch.provider,
        workspace_id=batch.workspace_id,
        requested_by=batch.requested_by,
        status=batch.status,
        crm_target_ids=batch.crm_target_ids or [],
        selection_hash=batch.selection_hash,
        idempotency_key=batch.idempotency_key,
        counts=batch.counts or {},
        reconciliation_summary=batch.reconciliation_summary or {},
        started_at=batch.started_at,
        completed_at=batch.completed_at,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        items=[crm_export_item_to_model(item) for item in items],
    )
