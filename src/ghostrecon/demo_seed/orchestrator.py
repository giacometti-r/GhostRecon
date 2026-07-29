import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.database import session_scope

from .crm_seed import _seed_crm
from .enrichment_seed import _seed_enrichment
from .ids import DEMO_SEED_IDS, DEMO_SEED_REPORTING_RESOURCES, DemoSeedIds
from .incident_seed import _seed_incidents
from .intelligence_seed import _seed_intelligence
from .persistence import _seeded_counts
from .safety import DemoSeedSafetyError, assert_demo_seed_allowed
from .sequence_seed import _seed_sequence_and_meeting


async def seed_demo_data(settings: Settings | None = None) -> DemoSeedIds:
    resolved = settings or get_settings()
    assert_demo_seed_allowed(resolved)
    async with session_scope(resolved) as session:
        await _upsert_demo_records(session)
    return DEMO_SEED_IDS


async def async_main() -> None:
    settings = get_settings()
    ids = await seed_demo_data(settings)
    counts = await _seeded_counts(settings)
    print("Seeded deterministic local demo data:")
    for table_name in DEMO_SEED_REPORTING_RESOURCES:
        print(f"  {table_name}: {counts[table_name]}")
    print(f"  cyber_event_id: {ids.cyber_event_id}")
    print(f"  security_incident_id: {ids.security_incident_id}")
    print(f"  meeting_handoff_id: {ids.meeting_handoff_id}")
    print(f"  crm_export_batch_id: {ids.crm_export_batch_id}")


def main() -> None:
    try:
        asyncio.run(async_main())
    except DemoSeedSafetyError as exc:
        raise SystemExit(str(exc)) from exc


async def _upsert_demo_records(session: AsyncSession) -> None:
    now, incident_observed, fresh_source, degraded_source = await _seed_intelligence(session)
    incident, review_incident, watch = await _seed_incidents(
        session, now, incident_observed, degraded_source
    )
    (
        account,
        contact,
        contact_candidate,
        domain_review_candidate,
        email_candidate,
    ) = await _seed_enrichment(
        session, now, incident_observed, fresh_source, degraded_source, incident, watch
    )
    export_target, retry_target, meeting_target = await _seed_crm(
        session,
        now,
        fresh_source,
        degraded_source,
        incident,
        review_incident,
        account,
        contact,
        contact_candidate,
        domain_review_candidate,
        email_candidate,
    )
    await _seed_sequence_and_meeting(
        session, now, account, contact, export_target, retry_target, meeting_target
    )
