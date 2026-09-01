from fastapi import Header, HTTPException, Query

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    CrmProspectList,
    SequenceCreateRequest,
    SequenceList,
    SequenceOut,
    SequenceUpdateRequest,
    UnsubscribeRequest,
)
from ghostrecon.services.sequencing import (
    archive_sequence,
    create_sequence,
    get_sequence,
    list_sequences,
    process_unsubscribe,
    search_crm_prospects,
    update_sequence,
)

from .dependencies import VERIFIED_ACTOR
from .registry import gateway_router, sequencing_router


@gateway_router.post("/v1/sequences", response_model=SequenceOut)
@sequencing_router.post("/v1/sequences", response_model=SequenceOut)
async def sequence_create(
    request: SequenceCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: str = VERIFIED_ACTOR,
) -> SequenceOut:
    try:
        return await create_sequence(
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@gateway_router.get("/v1/sequences", response_model=SequenceList)
@sequencing_router.get("/v1/sequences", response_model=SequenceList)
async def sequence_list(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> SequenceList:
    return await list_sequences(status=status, limit=limit, settings=get_settings())


@gateway_router.get("/v1/sequences/crm-prospects", response_model=CrmProspectList)
@sequencing_router.get("/v1/sequences/crm-prospects", response_model=CrmProspectList)
async def sequence_crm_prospect_list(
    query: str = Query(default=""),
    limit: int = Query(default=25, ge=1, le=25),
) -> CrmProspectList:
    return await search_crm_prospects(query=query, limit=limit, settings=get_settings())


@gateway_router.post("/v1/sequences/unsubscribe")
@sequencing_router.post("/v1/sequences/unsubscribe")
async def sequence_unsubscribe(
    request: UnsubscribeRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    return await process_unsubscribe(
        request,
        idempotency_key=idempotency_key,
        settings=get_settings(),
    )


from . import sequence_enrollments as _sequence_enrollments  # noqa: E402, F401


@gateway_router.get("/v1/sequences/{sequence_id}", response_model=SequenceOut)
@sequencing_router.get("/v1/sequences/{sequence_id}", response_model=SequenceOut)
async def sequence_detail(sequence_id: str) -> SequenceOut:
    sequence = await get_sequence(sequence_id, settings=get_settings())
    if sequence is None:
        raise HTTPException(status_code=404, detail="sequence not found")
    return sequence


@gateway_router.patch("/v1/sequences/{sequence_id}", response_model=SequenceOut)
@sequencing_router.patch("/v1/sequences/{sequence_id}", response_model=SequenceOut)
async def sequence_update(
    sequence_id: str,
    request: SequenceUpdateRequest,
    actor: str = VERIFIED_ACTOR,
) -> SequenceOut:
    try:
        sequence = await update_sequence(
            sequence_id,
            request,
            actor=actor,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if sequence is None:
        raise HTTPException(status_code=404, detail="sequence not found")
    return sequence


@gateway_router.delete("/v1/sequences/{sequence_id}", response_model=SequenceOut)
@sequencing_router.delete("/v1/sequences/{sequence_id}", response_model=SequenceOut)
async def sequence_delete(
    sequence_id: str,
    actor: str = VERIFIED_ACTOR,
) -> SequenceOut:
    sequence = await archive_sequence(sequence_id, actor=actor, settings=get_settings())
    if sequence is None:
        raise HTTPException(status_code=404, detail="sequence not found")
    return sequence
