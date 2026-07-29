from fastapi import APIRouter

gateway_router = APIRouter(tags=["gateway"])


crm_router = APIRouter(tags=["crm"])


ingestion_router = APIRouter(tags=["ingestion"])


enrichment_router = APIRouter(tags=["enrichment"])


email_router = APIRouter(tags=["email-intelligence"])


scoring_router = APIRouter(tags=["scoring-routing"])


sequencing_router = APIRouter(tags=["sequencing"])


meeting_router = APIRouter(tags=["meeting-handoff"])


governance_router = APIRouter(tags=["governance"])


console_router = APIRouter(tags=["console"])


reporting_router = APIRouter(tags=["reporting"])


event_intelligence_router = APIRouter(tags=["event-intelligence"])


incident_intelligence_router = APIRouter(tags=["incident-intelligence"])


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
