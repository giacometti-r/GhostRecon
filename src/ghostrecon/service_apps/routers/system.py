from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    SourceHealthList,
)
from ghostrecon.services.source_registry import list_source_health

from .registry import ROUTERS, event_intelligence_router, gateway_router, reporting_router


@gateway_router.get("/v1/service-map")
async def service_map() -> dict[str, list[str]]:
    return {
        "services": sorted(ROUTERS.keys()),
        "core_flow": [
            "event-intelligence",
            "incident-intelligence",
            "ingestion",
            "enrichment",
            "email-intelligence",
            "scoring-routing",
            "governance",
            "sequencing",
            "meeting-handoff",
            "crm",
            "reporting",
        ],
    }


@gateway_router.get("/v1/intelligence/sources/health", response_model=SourceHealthList)
@reporting_router.get("/v1/intelligence/sources/health", response_model=SourceHealthList)
@event_intelligence_router.get("/v1/intelligence/sources/health", response_model=SourceHealthList)
async def source_health(kind: str | None = None) -> SourceHealthList:
    return SourceHealthList(sources=await list_source_health(kind, get_settings()))
