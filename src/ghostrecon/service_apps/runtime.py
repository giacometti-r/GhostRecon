from uuid import uuid4

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import HTMLResponse

from ghostrecon.common.config import get_settings
from ghostrecon.common.security import verify_attio_signature
from ghostrecon.common.service import create_base_app
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    DomainEnrichmentRequest,
    EmailCandidateRequest,
    JobAccepted,
    PrepPacketRequest,
    ScoreRequest,
    SequenceEligibilityRequest,
    SourceHealthList,
    SuppressionCheckRequest,
)
from ghostrecon.services.email_candidates import generate_email_candidates
from ghostrecon.services.email_verifier import EmailVerifierClient
from ghostrecon.services.enrichment import enrich_domain
from ghostrecon.services.governance import evaluate_suppression
from ghostrecon.services.meeting import build_prep_packet
from ghostrecon.services.scoring import score_lead
from ghostrecon.services.sequencing import evaluate_sequence_eligibility
from ghostrecon.services.source_registry import list_source_health

settings = get_settings()
app = create_base_app(settings)
router = APIRouter()


@router.get("/v1/service-map", tags=["gateway"])
async def service_map() -> dict[str, list[str]]:
    return {
        "services": sorted(SERVICE_NAMES),
        "core_flow": [
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


@router.get("/v1/intelligence/sources/health", tags=["reporting"], response_model=SourceHealthList)
async def source_health(kind: str | None = None) -> SourceHealthList:
    return SourceHealthList(sources=await list_source_health(kind, settings))


@router.post("/v1/crm/sync/account", tags=["crm"])
async def crm_sync_account(payload: dict[str, object]) -> dict[str, object]:
    event = new_event(
        event_name=EventName.CRM_SYNCED,
        aggregate_type="account",
        aggregate_id=str(payload.get("account_id") or payload.get("crm_account_id") or uuid4()),
        source_service=settings.service_name,
        payload=payload,
    )
    return {"status": "queued", "event": event.model_dump(mode="json")}


@router.post("/webhooks/attio", status_code=202, tags=["ingestion"], response_model=None)
async def attio_webhook(
    request: Request,
    attio_signature: str | None = Header(default=None),
    x_attio_signature: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
) -> JobAccepted | Response:
    body = await request.body()
    signature = attio_signature or x_attio_signature
    if not verify_attio_signature(body, signature, settings.attio_webhook_secret):
        return Response(status_code=401)
    _ = idempotency_key or str(uuid4())
    return JobAccepted(job_id=uuid4())


@router.post("/v1/enrichment/domain", tags=["enrichment"])
async def domain_enrichment(request: DomainEnrichmentRequest):
    return await enrich_domain(request.domain)


@router.post("/v1/email/candidates", tags=["email-intelligence"])
async def email_candidates(request: EmailCandidateRequest):
    return {
        "candidates": [
            candidate.model_dump(mode="json")
            for candidate in generate_email_candidates(
                request.full_name, request.domain, request.known_patterns
            )
        ]
    }


@router.post("/v1/email/verify", tags=["email-intelligence"])
async def email_verify(payload: dict[str, object]) -> dict[str, object]:
    client = EmailVerifierClient(settings)
    if "emails" in payload and isinstance(payload["emails"], list):
        return await client.validate_batch(payload["emails"])  # type: ignore[arg-type]
    if "email" not in payload:
        raise ValueError("payload must include email or emails")
    return await client.validate(payload["email"])  # type: ignore[arg-type]


@router.post("/v1/scoring/lead", tags=["scoring-routing"])
async def lead_score(request: ScoreRequest):
    return score_lead(request)


@router.post("/v1/sequences/evaluate", tags=["sequencing"])
async def sequence_eligibility(request: SequenceEligibilityRequest):
    return evaluate_sequence_eligibility(request)


@router.post("/v1/meetings/prep-packet", tags=["meeting-handoff"])
async def prep_packet(request: PrepPacketRequest):
    return build_prep_packet(request)


@router.post("/v1/suppressions/evaluate", tags=["governance"])
async def suppression_check(request: SuppressionCheckRequest):
    return evaluate_suppression(request)


@router.get("/", response_class=HTMLResponse, tags=["console"])
async def console_home() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head><title>GhostRecon Console</title></head>
      <body>
        <h1>GhostRecon Console</h1>
        <p>Queues, approvals, replay controls, suppressions, and operational health live here.</p>
      </body>
    </html>
    """


@router.get("/v1/kpis/catalog", tags=["reporting"])
async def kpi_catalog() -> dict[str, list[str]]:
    return {
        "coverage": ["accounts_touched_per_rep", "buying_group_coverage", "enrichment_rate"],
        "speed": ["trigger_to_first_touch_seconds", "meeting_to_prep_packet_seconds"],
        "quality": ["bounce_rate", "duplicate_rate", "routing_error_rate"],
        "pipeline": ["meeting_to_sql_rate", "sql_to_opportunity_rate", "pipeline_created"],
        "ops_health": ["workflow_failure_rate", "replay_rate", "mttr_seconds", "sla_breaches"],
    }


SERVICE_NAMES = {
    "gateway-service",
    "crm-service",
    "ingestion-service",
    "enrichment-service",
    "email-intelligence-service",
    "scoring-routing-service",
    "sequencing-service",
    "meeting-handoff-service",
    "governance-service",
    "console-service",
    "reporting-service",
}

app.include_router(router)
