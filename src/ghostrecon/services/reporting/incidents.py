from __future__ import annotations

from sqlalchemy import or_, select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    ReportingIncidentDetail,
    ReportingIncidentList,
    ReportingOperatorContext,
    SecurityIncidentOut,
)
from ghostrecon.models.db import (
    SecurityIncident,
)
from ghostrecon.services.incident_intelligence import incident_to_api


async def get_reporting_incidents(
    *,
    status: str | None = None,
    source: str | None = None,
    company: str | None = None,
    attack_vector: str | None = None,
    incident_type: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingIncidentList:
    _ = operator
    offset = parse_cursor(cursor)
    async with session_scope(settings) as session:
        stmt = select(SecurityIncident).order_by(
            SecurityIncident.created_at.desc(),
            SecurityIncident.id.asc(),
        )
        if status:
            stmt = stmt.where(_fuzzy(SecurityIncident.status, status))
        if source:
            stmt = stmt.where(_fuzzy(SecurityIncident.source_definition_id, source))
        if company:
            stmt = stmt.where(
                or_(
                    _fuzzy(SecurityIncident.primary_affected_company, company),
                    _fuzzy(SecurityIncident.affected_companies, company),
                    _fuzzy(SecurityIncident.primary_affected_domain, company),
                    _fuzzy(SecurityIncident.affected_domains, company),
                )
            )
        if attack_vector:
            stmt = stmt.where(_fuzzy(SecurityIncident.attack_vector, attack_vector))
        if incident_type:
            stmt = stmt.where(_fuzzy(SecurityIncident.incident_type, incident_type))
        result = await session.execute(stmt.offset(offset).limit(limit + 1))
        rows = list(result.scalars())

    incidents = rows[:limit]
    metadata = await reporting_metadata(
        "incident",
        settings=settings,
        record_watermark_name="incident_updated_at",
        record_watermark=_latest_datetime(incident.updated_at for incident in incidents),
    )
    return ReportingIncidentList(
        metadata=metadata,
        incidents=[
            SecurityIncidentOut.model_validate(incident_to_api(incident)) for incident in incidents
        ],
        next_cursor=next_cursor(rows, limit, offset),
    )


async def get_reporting_incident_detail(
    incident_id: str,
    *,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingIncidentDetail | None:
    _ = operator
    async with session_scope(settings) as session:
        incident = await session.get(SecurityIncident, incident_id)
    if incident is None:
        return None
    metadata = await reporting_metadata(
        "incident",
        settings=settings,
        record_watermark_name="incident_updated_at",
        record_watermark=incident.updated_at,
    )
    return ReportingIncidentDetail(
        metadata=metadata,
        incident=SecurityIncidentOut.model_validate(incident_to_api(incident)),
    )


from .common import _fuzzy, next_cursor, parse_cursor, reporting_metadata  # noqa: E402
from .crm import _latest_datetime  # noqa: E402
