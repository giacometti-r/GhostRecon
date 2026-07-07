from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    CrmExportBatchOut,
    CrmExportCreateRequest,
    CrmExportItemOut,
    CrmExportRetryRequest,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    CrmExportBatch,
    CrmExportItem,
    CrmTarget,
    CyberEvent,
    EmailCandidateRecord,
    EventParticipant,
    OutboxEvent,
    SecurityIncident,
)
from ghostrecon.services.crm_attio import (
    AttioCrmClient,
    CrmClient,
    CrmExportPlan,
    CrmProviderError,
)

CRM_SERVICE_NAME = "crm-service"
EXPORTABLE_TARGET_STATUS = "pending_export"
EXPORTABLE_EXPORT_STATUSES = {"not_exported", "failed_retryable"}
SUCCESS_ITEM_STATUSES = {"succeeded", "reconciled"}
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
    crm_client = client or AttioCrmClient(resolved)
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
                    idempotency_key=(
                        f"crm_export.item_succeeded:{item.id}:{item.attempt_count}"
                    ),
                ),
            )

        _complete_batch(session, batch, await _batch_items(session, batch.id))
        return crm_export_batch_to_model(batch, await _batch_items(session, batch.id))


def selection_hash(target_ids: list[str]) -> str:
    payload = json.dumps(sorted(target_ids), separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


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


async def _plan_for_target(
    session: Any,
    target: CrmTarget,
    settings: Settings,
) -> CrmExportPlan:
    target_type = _normalize_target_type(target.target_type)
    if target_type == "cyber_event":
        event = await session.get(CyberEvent, target.target_id)
        if event is None:
            raise ValueError("event target does not exist")
        return CrmExportPlan(
            target_type=target.target_type,
            target_id=target.target_id,
            provider_object="cyber_events",
            stable_match_key=f"ghostrecon_event:{event.id}",
            matching_attribute="ghostrecon_id",
            values={
                "ghostrecon_id": event.id,
                "name": event.name,
                "event_series_key": event.event_series_key,
                "starts_at_utc": _iso(event.starts_at_utc),
                "country": event.country,
                "source_lineage": _lineage(target),
            },
            list_api_slug=settings.attio_events_list_api_slug,
            list_entry_values={"export_status": "approved"},
        )
    if target_type == "security_incident":
        incident = await session.get(SecurityIncident, target.target_id)
        if incident is None:
            raise ValueError("incident target does not exist")
        return CrmExportPlan(
            target_type=target.target_type,
            target_id=target.target_id,
            provider_object="security_incidents",
            stable_match_key=f"ghostrecon_incident:{incident.id}",
            matching_attribute="ghostrecon_id",
            values={
                "ghostrecon_id": incident.id,
                "title": incident.title,
                "status": incident.status,
                "attack_vector": incident.attack_vector,
                "affected_companies": incident.affected_companies or [],
                "evidence_source_item_ids": incident.evidence_source_item_ids or [],
                "source_lineage": _lineage(target),
            },
            list_api_slug=settings.attio_incidents_list_api_slug,
            list_entry_values={"export_status": "approved"},
        )
    if target_type == "company":
        account = await session.get(Account, target.target_id)
        if account is None:
            raise ValueError("company target does not exist")
        if not account.domain:
            raise PolicySkip("company export requires a stable domain")
        return CrmExportPlan(
            target_type=target.target_type,
            target_id=target.target_id,
            provider_object="companies",
            stable_match_key=f"domain:{account.domain.lower()}",
            matching_attribute="domains",
            values={
                "name": account.company_name,
                "domains": [{"domain": account.domain.lower()}],
                "ghostrecon_id": account.id,
                "source_lineage": _lineage(target),
            },
            list_api_slug=settings.attio_companies_list_api_slug,
            list_entry_values={"export_status": "approved"},
        )
    if target_type in {"contact", "email_candidate", "event_participant", "incident_contact"}:
        return await _person_plan(session, target, settings)
    raise ValueError(f"unsupported CRM export target type {target.target_type!r}")


async def _person_plan(
    session: Any,
    target: CrmTarget,
    settings: Settings,
) -> CrmExportPlan:
    target_type = _normalize_target_type(target.target_type)
    full_name = None
    title = None
    email = None
    source_url = None
    list_api_slug = settings.attio_incident_contacts_list_api_slug
    if target_type == "email_candidate":
        candidate = await session.get(EmailCandidateRecord, target.target_id)
        if candidate is None:
            raise ValueError("email-candidate target does not exist")
        if candidate.verification_status != "verified":
            raise PolicySkip("people export requires a verified business email")
        email = candidate.email
        contact = await session.get(Contact, candidate.contact_id) if candidate.contact_id else None
        full_name = contact.full_name if contact else None
        title = contact.title if contact else None
        source_url = contact.source_url if contact else None
    elif target_type == "contact":
        contact = await session.get(Contact, target.target_id)
        if contact is None:
            raise ValueError("contact target does not exist")
        if not contact.email or contact.email_status not in {None, "verified"}:
            raise PolicySkip("people export requires a verified business email")
        email = contact.email
        full_name = contact.full_name
        title = contact.title
        source_url = contact.source_url
    elif target_type == "event_participant":
        participant = await session.get(EventParticipant, target.target_id)
        if participant is None:
            raise ValueError("event-participant target does not exist")
        if not participant.crm_export_allowed:
            raise PolicySkip("participant source policy does not allow CRM export")
        full_name = participant.published_name
        title = participant.published_role
        source_url = participant.profile_url
        list_api_slug = settings.attio_event_participants_list_api_slug
    else:
        raise ValueError(f"unsupported people export target type {target.target_type!r}")

    stable_match_key = f"email:{email.lower()}" if email else f"ghostrecon_person:{target.id}"
    matching_attribute = "email_addresses" if email else "ghostrecon_id"
    values: dict[str, object] = {
        "ghostrecon_id": target.target_id,
        "name": full_name or target.target_id,
        "job_title": title,
        "source_url": source_url,
        "source_lineage": _lineage(target),
    }
    if email:
        values["email_addresses"] = [{"email_address": email.lower()}]
    return CrmExportPlan(
        target_type=target.target_type,
        target_id=target.target_id,
        provider_object="people",
        stable_match_key=stable_match_key,
        matching_attribute=matching_attribute,
        values=values,
        list_api_slug=list_api_slug,
        list_entry_values={"export_status": "approved"},
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
                f"crm_export.batch_completed:{batch.id}:"
                f"{sum(item.attempt_count for item in items)}"
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


def _normalize_target_type(target_type: str) -> str:
    aliases = {
        "event": "cyber_event",
        "cyber_event": "cyber_event",
        "incident": "security_incident",
        "security_incident": "security_incident",
        "account": "company",
        "company": "company",
        "organization": "company",
        "affected_company": "company",
        "contact": "contact",
        "incident_contact": "contact",
        "email_candidate": "email_candidate",
        "event_participant": "event_participant",
    }
    normalized = aliases.get(target_type, target_type)
    return normalized


def _provider_object_for_type(target_type: str) -> str:
    normalized = _normalize_target_type(target_type)
    if normalized == "cyber_event":
        return "cyber_events"
    if normalized == "security_incident":
        return "security_incidents"
    if normalized == "company":
        return "companies"
    if normalized in {"contact", "email_candidate", "event_participant", "incident_contact"}:
        return "people"
    return "people"


def _unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def _lineage(target: CrmTarget) -> dict[str, object]:
    return {
        "crm_target_id": target.id,
        "review_candidate_id": target.review_candidate_id,
        "review_decision_id": target.review_decision_id,
        "origin_type": target.origin_type,
        "origin_id": target.origin_id,
        "source_definition_id": target.source_definition_id,
        "source_item_ids": target.source_item_ids or [],
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def utcnow() -> datetime:
    return datetime.now(UTC)


class PolicySkip(ValueError):
    pass
