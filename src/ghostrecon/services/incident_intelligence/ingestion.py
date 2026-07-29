from __future__ import annotations

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.services.source_registry import fetch_source_by_id


async def fetch_incident_source(
    source_definition_id: str, settings: Settings | None = None
) -> dict[str, object]:
    fetch_result = await fetch_source_by_id(source_definition_id, settings)
    parse_result = await parse_pending_incident_items(source_definition_id, settings)
    return {"fetch": fetch_result, "parse": parse_result}


async def parse_pending_incident_items(
    source_definition_id: str | None = None, settings: Settings | None = None
) -> dict[str, object]:
    async with session_scope(settings) as session:
        repository = IncidentIntelligenceRepository(session)
        return await repository.parse_pending_items(source_definition_id)


from .repository import IncidentIntelligenceRepository  # noqa: E402
