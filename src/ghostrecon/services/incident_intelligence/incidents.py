from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    IncidentUpdateRequest,
    ManualIncidentCreate,
)
from ghostrecon.models.db import (
    AuditEvent,
    OutboxEvent,
    SecurityIncident,
)


async def list_incidents(
    *,
    status: str | None = None,
    source: str | None = None,
    company: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> list[SecurityIncident]:
    async with session_scope(settings) as session:
        repository = IncidentIntelligenceRepository(session)
        return await repository.list_incidents(
            status=status, source=source, company=company, limit=limit
        )


async def get_incident(
    incident_id: str, settings: Settings | None = None
) -> SecurityIncident | None:
    async with session_scope(settings) as session:
        return await session.get(SecurityIncident, incident_id)


async def create_manual_incident(
    payload: ManualIncidentCreate,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> list[SecurityIncident]:
    async with session_scope(settings) as session:
        group_key = f"manual-incident:{idempotency_key}"
        existing = list(
            (
                await session.execute(
                    select(SecurityIncident).where(SecurityIncident.incident_group_key == group_key)
                )
            ).scalars()
        )
        if existing:
            return existing
        incidents = []
        for index, (company, domain) in enumerate(
            _incident_contexts(payload.affected_companies, payload.affected_domains)
        ):
            dedupe_key = f"{group_key}:{index}:{_slug(company or domain or payload.title)}"
            incident = SecurityIncident(
                status="candidate",
                title=payload.title,
                incident_group_key=group_key,
                primary_affected_company=company,
                primary_affected_domain=domain,
                affected_companies=[company] if company else [],
                affected_domains=[domain] if domain else [],
                incident_type=payload.incident_type,
                attack_vector=payload.attack_vector,
                first_observed_at=payload.first_observed_at,
                last_observed_at=payload.last_observed_at or payload.first_observed_at,
                geography=list(payload.geography),
                languages=list(payload.languages),
                confidence=payload.confidence,
                evidence_article_ids=[],
                evidence_source_item_ids=list(payload.source_item_ids),
                evidence_families=["manual"],
                evidence_urls=list(payload.evidence_urls),
                corroboration_method="none",
                canonical_state="canonical",
                dedupe_key=dedupe_key,
                source_definition_id=None,
                source_item_ids=list(payload.source_item_ids),
                version=1,
            )
            session.add(incident)
            incidents.append(incident)
        await session.flush()
        for incident in incidents:
            session.add(
                AuditEvent(
                    actor=actor,
                    action="security_incident.manual_created",
                    entity_type="security_incident",
                    entity_id=incident.id,
                    idempotency_key=f"{idempotency_key}:{incident.id}",
                    payload={"source": "manual", "incident_group_key": group_key},
                )
            )
            self_event = new_event(
                event_name=EventName.SECURITY_INCIDENT_DETECTED,
                aggregate_type="security_incident",
                aggregate_id=incident.id,
                source_service=INCIDENT_SERVICE_NAME,
                source_item_ids=[str(item) for item in incident.source_item_ids],
                payload={
                    "security_incident_id": incident.id,
                    "incident_group_key": incident.incident_group_key,
                    "primary_affected_company": incident.primary_affected_company,
                    "manual": True,
                    "created_by": actor,
                },
                idempotency_key=f"security_incident.manual:{incident.id}",
            ).model_dump(mode="json")
            session.add(
                OutboxEvent(
                    event_name=self_event["event_name"],
                    aggregate_type=self_event["aggregate_type"],
                    aggregate_id=self_event["aggregate_id"],
                    idempotency_key=self_event["idempotency_key"],
                    payload=self_event,
                )
            )
        return incidents


async def update_incident(
    incident_id: str,
    payload: IncidentUpdateRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> SecurityIncident | None:
    async with session_scope(settings) as session:
        incident = await session.get(SecurityIncident, incident_id)
        if incident is None:
            return None
        if incident.version != payload.version:
            raise ValueError("incident version conflict")
        fields = payload.model_fields_set - {"version"}
        if "title" in fields and payload.title is not None:
            incident.title = payload.title
        if "affected_companies" in fields and payload.affected_companies is not None:
            incident.affected_companies = list(payload.affected_companies)
            incident.primary_affected_company = (
                payload.affected_companies[0] if payload.affected_companies else None
            )
        if "affected_domains" in fields and payload.affected_domains is not None:
            incident.affected_domains = list(payload.affected_domains)
            incident.primary_affected_domain = (
                payload.affected_domains[0] if payload.affected_domains else None
            )
        if "incident_type" in fields:
            incident.incident_type = payload.incident_type
        if "attack_vector" in fields:
            incident.attack_vector = payload.attack_vector
        if "first_observed_at" in fields:
            incident.first_observed_at = payload.first_observed_at
        if "last_observed_at" in fields:
            incident.last_observed_at = payload.last_observed_at
        if "geography" in fields and payload.geography is not None:
            incident.geography = list(payload.geography)
        if "languages" in fields and payload.languages is not None:
            incident.languages = list(payload.languages)
        if "source_item_ids" in fields and payload.source_item_ids is not None:
            incident.source_item_ids = list(payload.source_item_ids)
        if "evidence_urls" in fields and payload.evidence_urls is not None:
            incident.evidence_urls = list(payload.evidence_urls)
        if "confidence" in fields and payload.confidence is not None:
            incident.confidence = payload.confidence
        incident.version += 1
        incident.updated_at = datetime.now(UTC)
        session.add(
            AuditEvent(
                actor=actor,
                action="security_incident.updated",
                entity_type="security_incident",
                entity_id=incident.id,
                idempotency_key=idempotency_key,
                payload={"source": "dashboard"},
            )
        )
        return incident


from .candidates import INCIDENT_SERVICE_NAME  # noqa: E402
from .parsers import _incident_contexts, _slug  # noqa: E402
from .repository import IncidentIntelligenceRepository  # noqa: E402
