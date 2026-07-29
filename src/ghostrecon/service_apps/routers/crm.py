from uuid import uuid4

from fastapi import Header, HTTPException

from ghostrecon.common.config import get_settings
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    CrmExportBatchOut,
    CrmExportCreateRequest,
    CrmExportRetryRequest,
)
from ghostrecon.services.crm_exports import (
    get_crm_export_batch,
    retry_failed_crm_export_items,
    start_crm_export,
)

from .registry import crm_router, gateway_router


@crm_router.post("/v1/crm/sync/account")
async def crm_sync_account(payload: dict[str, object]) -> dict[str, object]:
    event = new_event(
        event_name=EventName.CRM_SYNCED,
        aggregate_type="account",
        aggregate_id=str(payload.get("account_id") or payload.get("crm_account_id") or uuid4()),
        source_service="crm-service",
        payload=payload,
    )
    return {"status": "queued", "event": event.model_dump(mode="json")}


@gateway_router.post("/v1/crm/exports", response_model=CrmExportBatchOut)
@crm_router.post("/v1/crm/exports", response_model=CrmExportBatchOut)
async def crm_export_start(
    request: CrmExportCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = Header(default="system", alias="X-Actor"),
) -> CrmExportBatchOut:
    try:
        return await start_crm_export(
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@gateway_router.get("/v1/crm/exports/{batch_id}", response_model=CrmExportBatchOut)
@crm_router.get("/v1/crm/exports/{batch_id}", response_model=CrmExportBatchOut)
async def crm_export_detail(batch_id: str) -> CrmExportBatchOut:
    batch = await get_crm_export_batch(batch_id, settings=get_settings())
    if batch is None:
        raise HTTPException(status_code=404, detail="crm export batch not found")
    return batch


@gateway_router.post("/v1/crm/exports/{batch_id}/retry-failed", response_model=CrmExportBatchOut)
@crm_router.post("/v1/crm/exports/{batch_id}/retry-failed", response_model=CrmExportBatchOut)
async def crm_export_retry_failed(
    batch_id: str,
    request: CrmExportRetryRequest | None = None,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    actor: str = Header(default="system", alias="X-Actor"),
) -> CrmExportBatchOut:
    try:
        batch = await retry_failed_crm_export_items(
            batch_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if batch is None:
        raise HTTPException(status_code=404, detail="crm export batch not found")
    return batch
