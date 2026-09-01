from fastapi import APIRouter

from ghostrecon.security.routing import SecurityRoute

gateway_router = APIRouter(tags=["gateway"], route_class=SecurityRoute)
crm_router = APIRouter(tags=["crm"], route_class=SecurityRoute)
ingestion_router = APIRouter(tags=["ingestion"], route_class=SecurityRoute)
enrichment_router = APIRouter(tags=["enrichment"], route_class=SecurityRoute)
email_router = APIRouter(tags=["email-intelligence"], route_class=SecurityRoute)
scoring_router = APIRouter(tags=["scoring-routing"], route_class=SecurityRoute)
sequencing_router = APIRouter(tags=["sequencing"], route_class=SecurityRoute)
meeting_router = APIRouter(tags=["meeting-handoff"], route_class=SecurityRoute)
governance_router = APIRouter(tags=["governance"], route_class=SecurityRoute)
console_router = APIRouter(tags=["console"], route_class=SecurityRoute)
reporting_router = APIRouter(tags=["reporting"], route_class=SecurityRoute)
event_intelligence_router = APIRouter(tags=["event-intelligence"], route_class=SecurityRoute)
incident_intelligence_router = APIRouter(tags=["incident-intelligence"], route_class=SecurityRoute)

ROUTERS = {
    "gateway-service": gateway_router,
    "crm-service": crm_router,
    "ingestion-service": ingestion_router,
    "enrichment-service": enrichment_router,
    "email-intelligence-service": email_router,
    "scoring-routing-service": scoring_router,
    "sequencing-service": sequencing_router,
    "meeting-handoff-service": meeting_router,
    "governance-service": governance_router,
    "console-service": console_router,
    "reporting-service": reporting_router,
    "event-intelligence-service": event_intelligence_router,
    "incident-intelligence-service": incident_intelligence_router,
}
