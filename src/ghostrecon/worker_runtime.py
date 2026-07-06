import asyncio

from celery import Celery

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import (
    ContactEnrichmentCreate,
    EmailCandidatePersistRequest,
    EmailVerifyBatchRequest,
    EntityResolutionCreate,
    SuppressionCheckRequest,
)
from ghostrecon.services.company_crawler import run_company_crawl
from ghostrecon.services.email_candidates import generate_email_candidates
from ghostrecon.services.enrichment_workflows import (
    contact_candidate_to_model,
    create_contact_enrichment_candidate,
    create_entity_resolution,
    email_candidate_to_model,
    entity_resolution_to_model,
    persist_email_candidates,
    verify_email_candidates,
)
from ghostrecon.services.event_intelligence import fetch_event_source, parse_pending_event_items
from ghostrecon.services.governance import evaluate_suppression
from ghostrecon.services.incident_intelligence import (
    fetch_incident_source,
    parse_pending_incident_items,
)
from ghostrecon.services.source_registry import fetch_source_by_id

settings = get_settings()

celery_app = Celery(
    "ghostrecon",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue=settings.service_name,
)


@celery_app.task(name="ghostrecon.process_attio_webhook")
def process_attio_webhook(payload: dict[str, object], idempotency_key: str) -> dict[str, object]:
    return {"status": "processed", "idempotency_key": idempotency_key, "payload": payload}


@celery_app.task(name="ghostrecon.generate_email_candidates")
def generate_email_candidate_task(full_name: str, domain: str) -> list[dict[str, object]]:
    return [
        candidate.model_dump(mode="json")
        for candidate in generate_email_candidates(full_name, domain)
    ]


@celery_app.task(name="ghostrecon.evaluate_suppression")
def evaluate_suppression_task(payload: dict[str, object]) -> dict[str, object]:
    result = evaluate_suppression(SuppressionCheckRequest.model_validate(payload))
    return result.model_dump(mode="json")


@celery_app.task(name="ghostrecon.crawl_company_domain")
def crawl_company_domain(domain: str) -> dict[str, object]:
    run_company_crawl(domain, settings.crawl_user_agent, settings.crawl_respect_robots)
    return {"status": "completed", "domain": domain}


@celery_app.task(name="ghostrecon.resolve_entity")
def resolve_entity_task(payload: dict[str, object], idempotency_key: str) -> dict[str, object]:
    case = asyncio.run(
        create_entity_resolution(
            EntityResolutionCreate.model_validate(payload),
            idempotency_key=idempotency_key,
            settings=settings,
        )
    )
    return entity_resolution_to_model(case).model_dump(mode="json")


@celery_app.task(name="ghostrecon.enrich_contact_candidate")
def enrich_contact_candidate_task(
    payload: dict[str, object], idempotency_key: str
) -> dict[str, object]:
    candidate = asyncio.run(
        create_contact_enrichment_candidate(
            ContactEnrichmentCreate.model_validate(payload),
            idempotency_key=idempotency_key,
            settings=settings,
        )
    )
    return contact_candidate_to_model(candidate).model_dump(mode="json")


@celery_app.task(name="ghostrecon.persist_email_candidates")
def persist_email_candidates_task(
    payload: dict[str, object], idempotency_key: str
) -> list[dict[str, object]]:
    candidates = asyncio.run(
        persist_email_candidates(
            EmailCandidatePersistRequest.model_validate(payload),
            idempotency_key=idempotency_key,
            settings=settings,
        )
    )
    return [email_candidate_to_model(candidate).model_dump(mode="json") for candidate in candidates]


@celery_app.task(name="ghostrecon.verify_email_candidates_batch")
def verify_email_candidates_batch_task(payload: dict[str, object]) -> list[dict[str, object]]:
    candidates = asyncio.run(
        verify_email_candidates(EmailVerifyBatchRequest.model_validate(payload), settings=settings)
    )
    return [email_candidate_to_model(candidate).model_dump(mode="json") for candidate in candidates]


@celery_app.task(name="ghostrecon.fetch_source")
def fetch_source_task(source_definition_id: str) -> dict[str, object]:
    return asyncio.run(fetch_source_by_id(source_definition_id, settings))


@celery_app.task(name="ghostrecon.fetch_event_source")
def fetch_event_source_task(source_definition_id: str) -> dict[str, object]:
    return asyncio.run(fetch_event_source(source_definition_id, settings))


@celery_app.task(name="ghostrecon.parse_pending_event_items")
def parse_pending_event_items_task(source_definition_id: str | None = None) -> dict[str, object]:
    return asyncio.run(parse_pending_event_items(source_definition_id, settings))


@celery_app.task(name="ghostrecon.fetch_incident_source")
def fetch_incident_source_task(source_definition_id: str) -> dict[str, object]:
    return asyncio.run(fetch_incident_source(source_definition_id, settings))


@celery_app.task(name="ghostrecon.parse_pending_incident_items")
def parse_pending_incident_items_task(source_definition_id: str | None = None) -> dict[str, object]:
    return asyncio.run(parse_pending_incident_items(source_definition_id, settings))
