from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName
from ghostrecon.models.api import (
    MeetingHandoffOut,
    PrepPacketRequest,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    CrmTarget,
    CyberEvent,
    MeetingHandoff,
    MeetingPrepPacket,
    SecurityIncident,
    Signal,
)


async def generate_meeting_prep_packet(
    meeting_id: str,
    *,
    actor: str,
    idempotency_key: str | None = None,
    settings: Settings | None = None,
) -> MeetingHandoffOut | None:
    async with session_scope(settings) as session:
        meeting = await session.get(MeetingHandoff, meeting_id)
        if meeting is None:
            return None
        if idempotency_key:
            existing = await session.scalar(
                select(MeetingPrepPacket).where(
                    MeetingPrepPacket.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                return await _meeting_to_model_with_children(session, meeting)

        existing_latest = await _latest_prep_packet(session, meeting.id)
        if existing_latest is not None and idempotency_key is None:
            return await _meeting_to_model_with_children(session, meeting)

        prep_request, source_snapshot = await _prep_request_for_meeting(session, meeting)
        packet = build_prep_packet(prep_request)
        now = utcnow()
        record = MeetingPrepPacket(
            meeting_id=meeting.id,
            account_summary=packet.account_summary,
            stakeholder_map=list(packet.stakeholder_map),
            likely_security_priorities=list(packet.likely_security_priorities),
            suggested_questions=list(packet.suggested_questions),
            risks=list(packet.risks),
            source_snapshot=source_snapshot,
            generated_by=actor,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        await session.flush()
        _enqueue_event(
            session,
            EventName.MEETING_PREP_PACKET_GENERATED,
            "meeting_prep_packet",
            record.id,
            meeting_prep_packet_to_api(record),
            f"meeting.prep_packet_generated:{record.id}",
        )
        return await _meeting_to_model_with_children(session, meeting)


async def _prep_request_for_meeting(
    session: Any,
    meeting: MeetingHandoff,
) -> tuple[PrepPacketRequest, dict[str, object]]:
    account = await session.get(Account, meeting.account_id) if meeting.account_id else None
    contact = await session.get(Contact, meeting.contact_id) if meeting.contact_id else None
    if account is None and contact and contact.account_id:
        account = await session.get(Account, contact.account_id)

    contacts = []
    if account is not None:
        result = await session.execute(
            select(Contact).where(Contact.account_id == account.id).order_by(Contact.full_name)
        )
        contacts = list(result.scalars())
    elif contact is not None:
        contacts = [contact]

    signals = []
    if account is not None:
        result = await session.execute(
            select(Signal)
            .where(Signal.account_id == account.id)
            .order_by(Signal.signal_timestamp.desc())
            .limit(25)
        )
        signals = list(result.scalars())

    target = await session.get(CrmTarget, meeting.crm_target_id) if meeting.crm_target_id else None
    account_payload = (
        {
            "id": account.id,
            "company_name": account.company_name,
            "domain": account.domain,
            "industry": account.industry,
            "security_stack": account.security_stack or {},
        }
        if account is not None
        else {"company_name": "Account"}
    )
    contact_payloads = [
        {
            "id": item.id,
            "full_name": item.full_name,
            "title": item.title,
            "email": item.email,
            "persona_type": item.persona_type,
            "buying_role": item.buying_role,
        }
        for item in contacts
    ]
    signal_payloads = [
        {
            "id": item.id,
            "signal_type": item.signal_type,
            "signal_topic": item.signal_topic,
            "signal_strength": item.signal_strength,
            "product_relevance": item.product_relevance,
            "recommended_play": item.recommended_play,
        }
        for item in signals
    ]
    signal_payloads.extend(await _target_signals(session, target))
    source_snapshot = {
        "account_id": account.id if account else None,
        "contact_ids": [item.id for item in contacts],
        "signal_ids": [item.id for item in signals],
        "crm_target_id": meeting.crm_target_id,
        "crm_target_type": target.target_type if target else None,
        "crm_target_target_id": target.target_id if target else None,
    }
    return (
        PrepPacketRequest(
            account=account_payload,
            contacts=contact_payloads,
            signals=signal_payloads,
            meeting_time=meeting.start_at,
        ),
        source_snapshot,
    )


async def _target_signals(session: Any, target: CrmTarget | None) -> list[dict[str, object]]:
    if target is None:
        return []
    if target.target_type in {"security_incident", "incident"}:
        incident = await session.get(SecurityIncident, target.target_id)
        if incident is None:
            return []
        return [
            {
                "signal_type": "security_incident",
                "signal_topic": incident.title,
                "signal_strength": incident.confidence,
                "product_relevance": incident.attack_vector,
            }
        ]
    if target.target_type in {"cyber_event", "event"}:
        event = await session.get(CyberEvent, target.target_id)
        if event is None:
            return []
        return [
            {
                "signal_type": "cyber_event",
                "signal_topic": event.name,
                "signal_strength": event.confidence,
                "product_relevance": ", ".join(str(topic) for topic in event.topics or []),
            }
        ]
    return []


from .common import utcnow  # noqa: E402
from .crm_sync import _latest_prep_packet  # noqa: E402
from .events import _enqueue_event  # noqa: E402
from .lifecycle import build_prep_packet  # noqa: E402
from .serializers import _meeting_to_model_with_children, meeting_prep_packet_to_api  # noqa: E402
