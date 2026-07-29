from __future__ import annotations

from datetime import datetime
from typing import Any

from ghostrecon.common.config import Settings
from ghostrecon.models.db import (
    Account,
    Contact,
    CrmTarget,
    CyberEvent,
    EmailCandidateRecord,
    EventParticipant,
    SecurityIncident,
)
from ghostrecon.services.crm_attio import (
    CrmExportPlan,
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


class PolicySkip(ValueError):
    pass
