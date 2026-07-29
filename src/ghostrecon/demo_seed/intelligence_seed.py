from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.models.db import (
    CyberEvent,
    EventParticipant,
)

from .ids import DEMO_SEED_IDS, _slug
from .incident_seed import _source
from .persistence import _get_or_create


async def _seed_intelligence(session: AsyncSession):
    now = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    event_start = now + timedelta(days=30)
    incident_observed = now - timedelta(days=5)
    stale_success = now - timedelta(days=4)

    fresh_source = await _source(
        session,
        DEMO_SEED_IDS.fresh_source_definition_id,
        now=now,
        name="GhostRecon Local Demo Fresh Event Source",
        source_kind="event",
        adapter_type="fixture",
        operating_state="enabled",
        last_success_at=now,
        consecutive_failures=0,
        last_error=None,
        checkpoint_state={"cursor": "events-demo-2026-01-15", "seeded": True},
    )
    degraded_source = await _source(
        session,
        DEMO_SEED_IDS.degraded_source_definition_id,
        now=now,
        name="GhostRecon Local Demo Degraded Incident Source",
        source_kind="incident",
        adapter_type="fixture",
        operating_state="degraded",
        last_success_at=stale_success,
        consecutive_failures=2,
        last_error="Synthetic selector failure for stale/degraded dashboard demo.",
        checkpoint_state={"cursor": "incidents-demo-2026-01-11", "seeded": True},
    )
    await session.flush()

    event = await _get_or_create(session, CyberEvent, DEMO_SEED_IDS.cyber_event_id)
    event.name = "Cloud Security Summit Demo"
    event.event_series_key = "cloud-security-summit-demo"
    event.external_id = "demo-event-001"
    event.canonical_url = "https://ghostrecon.local/demo/events/cloud-security-summit"
    event.original_start = event_start.isoformat()
    event.original_end = (event_start + timedelta(days=2)).isoformat()
    event.source_timezone = "UTC"
    event.iana_timezone = "UTC"
    event.timezone_status = "resolved"
    event.starts_at_utc = event_start
    event.ends_at_utc = event_start + timedelta(days=2)
    event.event_format = "in-person"
    event.venue_name = "Demo Convention Center"
    event.street_address = "Demo Way 42"
    event.city = "Zurich"
    event.region = "ZH"
    event.postcode = "8001"
    event.country = "CH"
    event.virtual_url = None
    event.latitude = 47.3769
    event.longitude = 8.5417
    event.geocode_status = "resolved"
    event.geocode_provider = "local_demo"
    event.geocode_display_name = "Demo Convention Center, Demo Way 42, 8001 Zurich, CH"
    event.geocoded_at = now
    event.topics = ["cloud security", "incident response", "identity"]
    event.organizers = [{"name": "GhostRecon Demo Team"}]
    event.confidence = 92
    event.canonical_state = "canonical"
    event.dedupe_key = "demo:sprint15:event:cloud-security-summit"
    event.source_definition_id = fresh_source.id
    event.source_item_ids = []
    event.version = 1
    event.created_at = now
    event.updated_at = now
    await session.flush()

    participant = await _get_or_create(
        session, EventParticipant, DEMO_SEED_IDS.event_participant_id
    )
    participant.cyber_event_id = event.id
    participant.source_definition_id = fresh_source.id
    participant.source_item_id = None
    participant.source_participant_id = "demo-participant-001"
    participant.published_name = "Morgan Lee"
    participant.organization = "Example Industries"
    participant.published_role = "Director of Security Operations"
    participant.participant_type = "speaker"
    participant.profile_url = "https://ghostrecon.local/demo/people/morgan-lee"
    participant.reuse_state = "allowed"
    participant.reuse_evidence = {"basis": "synthetic local fixture"}
    participant.contact_extraction_allowed = True
    participant.crm_export_allowed = True
    participant.resolution_confidence = 94
    participant.dedupe_key = "demo:sprint15:participant:morgan-lee"
    participant.created_at = now
    participant.updated_at = now

    second_event = await _get_or_create(session, CyberEvent, DEMO_SEED_IDS.secondary_cyber_event_id)
    second_event.name = "Identity Defense Forum Demo"
    second_event.event_series_key = "identity-defense-forum-demo"
    second_event.external_id = "demo-event-002"
    second_event.canonical_url = "https://ghostrecon.local/demo/events/identity-defense-forum"
    second_event.original_start = (event_start + timedelta(days=12)).isoformat()
    second_event.original_end = (event_start + timedelta(days=13)).isoformat()
    second_event.source_timezone = "America/Los_Angeles"
    second_event.iana_timezone = "America/Los_Angeles"
    second_event.timezone_status = "resolved"
    second_event.starts_at_utc = event_start + timedelta(days=12)
    second_event.ends_at_utc = event_start + timedelta(days=13)
    second_event.event_format = "hybrid"
    second_event.venue_name = "Demo Security Exchange"
    second_event.street_address = "1 Market St"
    second_event.city = "San Francisco"
    second_event.region = "CA"
    second_event.postcode = "94105"
    second_event.country = "US"
    second_event.virtual_url = "https://ghostrecon.local/demo/events/identity-defense-forum/join"
    second_event.latitude = 37.7936
    second_event.longitude = -122.3959
    second_event.geocode_status = "resolved"
    second_event.geocode_provider = "local_demo"
    second_event.geocode_display_name = "1 Market St, San Francisco, CA 94105, US"
    second_event.geocoded_at = now
    second_event.topics = ["identity", "zero trust", "phishing"]
    second_event.organizers = [{"name": "GhostRecon Demo Team"}]
    second_event.confidence = 89
    second_event.canonical_state = "canonical"
    second_event.dedupe_key = "demo:sprint22:event:identity-defense-forum"
    second_event.source_definition_id = fresh_source.id
    second_event.source_item_ids = []
    second_event.version = 1
    second_event.created_at = now
    second_event.updated_at = now

    for participant_id, name, organization, role, participant_type in [
        (
            DEMO_SEED_IDS.secondary_event_participant_id,
            "Samira Owens",
            "Nimbus Retail",
            "CISO",
            "speaker",
        ),
        (
            DEMO_SEED_IDS.tertiary_event_participant_id,
            "Leo Martin",
            "Contoso Manufacturing",
            "Security Architect",
            "attendee",
        ),
    ]:
        extra_participant = await _get_or_create(session, EventParticipant, participant_id)
        extra_participant.cyber_event_id = second_event.id
        extra_participant.source_definition_id = fresh_source.id
        extra_participant.source_item_id = None
        extra_participant.source_participant_id = f"demo-{participant_id}"
        extra_participant.published_name = name
        extra_participant.organization = organization
        extra_participant.published_role = role
        extra_participant.participant_type = participant_type
        extra_participant.profile_url = f"https://ghostrecon.local/demo/people/{_slug(name)}"
        extra_participant.reuse_state = "allowed"
        extra_participant.reuse_evidence = {"basis": "synthetic local fixture"}
        extra_participant.contact_extraction_allowed = True
        extra_participant.crm_export_allowed = False
        extra_participant.resolution_confidence = 86
        extra_participant.dedupe_key = f"demo:sprint22:participant:{_slug(name)}"
        extra_participant.created_at = now
        extra_participant.updated_at = now
    return now, incident_observed, fresh_source, degraded_source
