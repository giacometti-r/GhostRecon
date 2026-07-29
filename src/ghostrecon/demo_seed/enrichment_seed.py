from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ghostrecon.models.db import (
    Account,
    Contact,
    ContactEnrichmentCandidate,
    EmailCandidateRecord,
    EntityResolutionCase,
    SecurityIncident,
    SourceDefinition,
    WatchTarget,
)

from .ids import DEMO_SEED_IDS
from .incident_seed import _watch_monitoring_run
from .persistence import _get_or_create


async def _contact_candidate(
    session: AsyncSession,
    record_id: str,
    *,
    now: datetime,
    resolution: EntityResolutionCase,
    account: Account,
    contact: Contact | None,
    incident: SecurityIncident,
    source_definition_id: str,
    published_name: str,
    title: str,
    role_scope: str,
    domain: str | None,
    profile_url: str,
    status: str,
    review_reason: str | None,
    idempotency_key: str,
) -> ContactEnrichmentCandidate:
    candidate = await _get_or_create(session, ContactEnrichmentCandidate, record_id)
    candidate.entity_resolution_case_id = resolution.id
    candidate.account_id = account.id
    candidate.contact_id = contact.id if contact else None
    candidate.origin_type = "security_incident"
    candidate.origin_id = incident.id
    candidate.published_name = published_name
    candidate.organization = account.company_name
    candidate.title = title
    candidate.role_scope = role_scope
    candidate.domain = domain
    candidate.profile_url = profile_url
    candidate.source_url = profile_url
    candidate.status = status
    candidate.eligibility_reason = review_reason
    candidate.reuse_state = "allowed"
    candidate.source_definition_id = source_definition_id
    candidate.source_item_ids = [f"{idempotency_key}:raw-demo"]
    candidate.policy_snapshot = {"lawful_basis": "synthetic_demo", "source_policy": "allowed"}
    candidate.candidate_payload = {
        "watch_target_id": DEMO_SEED_IDS.watch_target_id,
        "search_query": (
            'site:linkedin.com/in ("Head of Cybersecurity" OR "CISO" OR '
            '"Chief Information Security Officer" OR "CTO" OR "Chief Technology Officer") '
            f'"{account.company_name}"'
        ),
        "domain_discovery": {
            "query": f"{account.company_name} official website",
            "selected_domain": domain,
        },
    }
    candidate.review_reason = review_reason
    candidate.idempotency_key = idempotency_key
    candidate.version = 1
    candidate.created_at = now
    candidate.updated_at = now
    return candidate


async def _email_candidate(
    session: AsyncSession,
    *,
    now: datetime,
    contact: Contact,
    incident: SecurityIncident,
    source_definition_id: str,
) -> EmailCandidateRecord:
    candidate = await _get_or_create(
        session, EmailCandidateRecord, DEMO_SEED_IDS.email_candidate_id
    )
    candidate.contact_id = contact.id
    candidate.email = "avery.patel@example-industries.test"
    candidate.pattern = "{first}.{last}"
    candidate.verification_status = "needs_review"
    candidate.verification_payload = {"catch_all": True, "status": "unknown"}
    candidate.verification_checked_at = now
    candidate.source_definition_id = source_definition_id
    candidate.source_item_ids = [f"{incident.id}:email-demo"]
    candidate.origin_type = "security_incident"
    candidate.origin_id = incident.id
    candidate.policy_snapshot = {"lawful_basis": "synthetic_demo"}
    candidate.review_status = "needs_review"
    candidate.review_reason = "catch_all_domain"
    candidate.idempotency_key = "demo:sprint20:email-candidate:avery-patel"
    candidate.version = 1
    candidate.created_at = now
    return candidate


async def _seed_enrichment(
    session: AsyncSession,
    now: datetime,
    incident_observed: datetime,
    fresh_source: SourceDefinition,
    degraded_source: SourceDefinition,
    incident: SecurityIncident,
    watch: WatchTarget,
):
    account = await _get_or_create(session, Account, DEMO_SEED_IDS.account_id)
    account.crm_account_id = "attio-demo-account-example-industries"
    account.domain = "example-industries.test"
    account.company_name = "Example Industries"
    account.hq_country = "US"
    account.employee_count = 1800
    account.revenue_band = "100m-500m"
    account.industry = "Manufacturing"
    account.sub_industry = "Industrial equipment"
    account.tech_stack = {"cloud": ["aws"], "identity": ["okta"]}
    account.security_stack = {"siem": "demo-siem"}
    account.intent_topics = ["identity hardening", "incident response"]
    account.territory = "NA enterprise"
    account.owner_id = "demo-ae"
    account.named_account_flag = True
    account.priority_tier = "tier_1"
    account.fit_score = 86
    account.intent_score = 79
    account.composite_score = 83
    account.last_signal_at = incident_observed
    account.created_at = now
    account.updated_at = now
    await session.flush()

    contact = await _get_or_create(session, Contact, DEMO_SEED_IDS.contact_id)
    contact.crm_contact_id = "attio-demo-contact-taylor-ng"
    contact.account_id = account.id
    contact.full_name = "Taylor Ng"
    contact.title = "VP Security"
    contact.seniority = "executive"
    contact.function = "security"
    contact.email = "taylor.ng@example-industries.test"
    contact.email_status = "verified"
    contact.phone = None
    contact.linkedin_url = "https://ghostrecon.local/demo/people/taylor-ng"
    contact.timezone = "America/New_York"
    contact.persona_type = "economic_buyer"
    contact.buying_role = "decision_maker"
    contact.last_enriched_at = now
    contact.do_not_contact_flag = False
    contact.lawful_basis = "legitimate_interest"
    contact.source_vendor = "ghostrecon-demo"
    contact.source_confidence = 97
    contact.source_url = "https://ghostrecon.local/demo/contacts/taylor-ng"
    contact.source_definition_id = fresh_source.id
    contact.source_item_ids = []
    contact.origin_type = "security_incident"
    contact.origin_id = incident.id
    contact.source_policy_snapshot = {"lawful_basis": "synthetic_demo"}
    contact.review_status = "approved"
    contact.review_reason = None
    contact.idempotency_key = "demo:sprint15:contact:taylor-ng"
    contact.version = 1
    contact.created_at = now
    contact.updated_at = now
    await session.flush()

    resolution = await _get_or_create(
        session, EntityResolutionCase, DEMO_SEED_IDS.entity_resolution_case_id
    )
    resolution.origin_type = "security_incident"
    resolution.origin_id = incident.id
    resolution.entity_kind = "organization"
    resolution.input_name = "Example Industries"
    resolution.input_domain = "example-industries.test"
    resolution.resolved_account_id = account.id
    resolution.resolved_name = account.company_name
    resolution.resolved_domain = account.domain
    resolution.status = "resolved"
    resolution.confidence = 100
    resolution.alternatives = [{"account_id": account.id, "domain": account.domain}]
    resolution.source_definition_id = degraded_source.id
    resolution.source_item_ids = [f"{incident.id}:raw-demo"]
    resolution.policy_snapshot = {"lawful_basis": "synthetic_demo"}
    resolution.review_reason = None
    resolution.idempotency_key = "demo:sprint20:entity-resolution:example-industries"
    resolution.version = 1
    resolution.created_at = now
    resolution.updated_at = now
    await session.flush()

    contact_candidate = await _contact_candidate(
        session,
        DEMO_SEED_IDS.contact_candidate_id,
        now=now,
        resolution=resolution,
        account=account,
        contact=contact,
        incident=incident,
        source_definition_id=degraded_source.id,
        published_name="Avery Patel",
        title="Chief Information Security Officer",
        role_scope="security",
        domain="example-industries.test",
        profile_url="https://www.linkedin.com/in/avery-patel-ciso",
        status="eligible",
        review_reason=None,
        idempotency_key="demo:sprint20:contact-candidate:avery-patel",
    )
    domain_review_candidate = await _contact_candidate(
        session,
        DEMO_SEED_IDS.domain_review_contact_candidate_id,
        now=now,
        resolution=resolution,
        account=account,
        contact=None,
        incident=incident,
        source_definition_id=degraded_source.id,
        published_name="Jordan Kim",
        title="Head of Cybersecurity",
        role_scope="security",
        domain=None,
        profile_url="https://www.linkedin.com/in/jordan-kim-security",
        status="needs_review",
        review_reason="domain_discovery_failed",
        idempotency_key="demo:sprint20:contact-candidate:jordan-kim",
    )
    email_candidate = await _email_candidate(
        session,
        now=now,
        contact=contact,
        incident=incident,
        source_definition_id=degraded_source.id,
    )
    await _watch_monitoring_run(session, now=now, watch=watch)
    return account, contact, contact_candidate, domain_review_candidate, email_candidate
