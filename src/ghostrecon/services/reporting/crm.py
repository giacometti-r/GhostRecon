from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    CrmTargetOut,
    DashboardRole,
    ReportingCrmTargetDetail,
    ReportingCrmTargetList,
    ReportingOperatorContext,
    ReviewCandidateOut,
    WatchTargetOut,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    CrmTarget,
    EmailCandidateRecord,
    ReviewCandidate,
    WatchTarget,
)
from ghostrecon.services.enrichment_workflows import review_candidate_to_api
from ghostrecon.services.governance import crm_target_to_api
from ghostrecon.services.incident_intelligence import watch_target_to_api


async def get_reporting_crm_targets(
    *,
    status: str | None = None,
    target_type: str | None = None,
    export_status: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingCrmTargetList:
    context = operator or ReportingOperatorContext()
    offset = parse_cursor(cursor)
    async with session_scope(settings) as session:
        stmt = select(CrmTarget).order_by(CrmTarget.created_at.desc(), CrmTarget.id.asc())
        if status:
            stmt = stmt.where(_fuzzy(CrmTarget.status, status))
        if target_type:
            stmt = stmt.where(_fuzzy(CrmTarget.target_type, target_type))
        if export_status:
            stmt = stmt.where(_fuzzy(CrmTarget.export_status, export_status))
        result = await session.execute(stmt.offset(offset).limit(limit + 1))
        rows = list(result.scalars())
        targets = rows[:limit]
        projected_targets = [
            project_crm_target(
                target,
                context,
                display_fields=await _crm_target_display_fields(session, target),
            )
            for target in targets
        ]

    metadata = await reporting_metadata(
        None,
        settings=settings,
        record_watermark_name="crm_target_updated_at",
        record_watermark=_latest_datetime(target.updated_at for target in targets),
    )
    return ReportingCrmTargetList(
        metadata=metadata,
        crm_targets=projected_targets,
        next_cursor=next_cursor(rows, limit, offset),
    )


async def get_reporting_crm_target_detail(
    crm_target_id: str,
    *,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingCrmTargetDetail | None:
    context = operator or ReportingOperatorContext()
    async with session_scope(settings) as session:
        target = await session.get(CrmTarget, crm_target_id)
        display_fields = (
            await _crm_target_display_fields(session, target) if target is not None else {}
        )
    if target is None:
        return None
    metadata = await reporting_metadata(
        None,
        settings=settings,
        record_watermark_name="crm_target_updated_at",
        record_watermark=target.updated_at,
    )
    return ReportingCrmTargetDetail(
        metadata=metadata,
        crm_target=project_crm_target(target, context, display_fields=display_fields),
    )


def project_review_candidate(
    candidate: ReviewCandidate,
    context: ReportingOperatorContext,
) -> ReviewCandidateOut:
    payload = review_candidate_to_api(candidate)
    if context.role == DashboardRole.VIEWER:
        payload["reason"] = None
        payload["evidence_summary"] = {}
        payload["policy_snapshot"] = {}
        payload["policy_snapshot_hash"] = None
    return ReviewCandidateOut.model_validate(payload)


def project_watch_target(
    target: WatchTarget,
    context: ReportingOperatorContext,
) -> WatchTargetOut:
    payload = watch_target_to_api(target)
    if context.role != DashboardRole.GOVERNANCE_REVIEWER:
        payload["origin_incident_id"] = None
    return WatchTargetOut.model_validate(payload)


def project_crm_target(
    target: CrmTarget,
    context: ReportingOperatorContext,
    *,
    display_fields: dict[str, object] | None = None,
) -> CrmTargetOut:
    payload = crm_target_to_api(target)
    payload.update({key: value for key, value in (display_fields or {}).items() if value})
    if context.role == DashboardRole.VIEWER:
        payload["policy_snapshot"] = {}
        payload["approval_snapshot"] = {}
    return CrmTargetOut.model_validate(payload)


async def _crm_target_display_fields(session: Any, target: CrmTarget) -> dict[str, object]:
    fields: dict[str, object] = {
        "display_name": target.approval_snapshot.get("name")
        if isinstance(target.approval_snapshot, dict)
        else None,
        "company_name": target.approval_snapshot.get("company")
        if isinstance(target.approval_snapshot, dict)
        else None,
        "email": target.approval_snapshot.get("email")
        if isinstance(target.approval_snapshot, dict)
        else None,
    }
    policy = target.policy_snapshot if isinstance(target.policy_snapshot, dict) else {}
    fields["display_name"] = fields.get("display_name") or policy.get("name")
    fields["company_name"] = fields.get("company_name") or policy.get("company")
    fields["email"] = fields.get("email") or policy.get("email")

    if target.target_type == "contact":
        contact = await session.get(Contact, target.target_id)
        if contact is not None:
            fields["display_name"] = fields.get("display_name") or contact.full_name
            fields["email"] = fields.get("email") or contact.email
            if not fields.get("company_name") and contact.account_id:
                account = await session.get(Account, contact.account_id)
                if account is not None:
                    fields["company_name"] = account.company_name
    elif target.target_type == "email_candidate":
        email_candidate = await session.get(EmailCandidateRecord, target.target_id)
        if email_candidate is not None:
            fields["email"] = fields.get("email") or email_candidate.email
            if email_candidate.contact_id:
                contact = await session.get(Contact, email_candidate.contact_id)
                if contact is not None:
                    fields["display_name"] = fields.get("display_name") or contact.full_name
                    if not fields.get("company_name") and contact.account_id:
                        account = await session.get(Account, contact.account_id)
                        if account is not None:
                            fields["company_name"] = account.company_name

    if not fields.get("display_name"):
        fields["display_name"] = fields.get("email") or target.target_id
    return fields


def _latest_datetime(values: Any) -> datetime | None:
    dates = [value for value in values if isinstance(value, datetime)]
    if not dates:
        return None
    return max(dates)


from .common import _fuzzy, next_cursor, parse_cursor, reporting_metadata  # noqa: E402
