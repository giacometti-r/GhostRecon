import asyncio

from celery import Celery

from ghostrecon.common.config import get_settings
from ghostrecon.models.api import SuppressionCheckRequest
from ghostrecon.services.company_crawler import run_company_crawl
from ghostrecon.services.email_candidates import generate_email_candidates
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
