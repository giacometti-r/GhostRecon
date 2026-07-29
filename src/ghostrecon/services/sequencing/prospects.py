from __future__ import annotations

from sqlalchemy import select

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    CrmProspectList,
    CrmProspectOut,
    SequenceCrmProspectImportRequest,
    SequenceEnrollmentCreateRequest,
    SequenceEnrollmentOut,
)
from ghostrecon.models.db import (
    Account,
    Contact,
    CrmTarget,
)
from ghostrecon.services.crm_exports import crm_client_for_settings


async def search_crm_prospects(
    *,
    query: str,
    limit: int = 25,
    settings: Settings | None = None,
) -> CrmProspectList:
    resolved = settings or get_settings()
    client = crm_client_for_settings(resolved)
    prospects = await client.search_prospects(query, limit=limit)
    return CrmProspectList(
        prospects=[
            CrmProspectOut(
                provider_record_id=prospect.provider_record_id,
                provider_object=prospect.provider_object,
                display_name=prospect.display_name,
                email=prospect.email,
                title=prospect.title,
                company_name=prospect.company_name,
                company_domain=prospect.company_domain,
                source_payload=dict(prospect.source_payload),
            )
            for prospect in prospects
            if prospect.provider_record_id
        ],
        provider="attio" if resolved.attio_access_token else "local-demo",
    )


async def import_crm_prospect_to_sequence(
    request: SequenceCrmProspectImportRequest,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> SequenceEnrollmentOut:
    if not request.outreach_approved:
        raise ValueError("separate outreach approval is required")
    resolved = settings or get_settings()
    client = crm_client_for_settings(resolved)
    prospect = await client.get_prospect(request.provider_record_id)
    if prospect is None:
        matches = await client.search_prospects(request.provider_record_id, limit=25)
        prospect = next(
            (
                candidate
                for candidate in matches
                if candidate.provider_record_id == request.provider_record_id
            ),
            None,
        )
    if prospect is None:
        raise ValueError("CRM prospect not found")
    if not prospect.email:
        raise ValueError("CRM prospect requires an email before sequence assignment")
    domain = (
        prospect.company_domain or _domain_from_email(prospect.email) or "unknown.local"
    ).lower()
    now = utcnow()
    async with session_scope(resolved) as session:
        account = await session.scalar(select(Account).where(Account.domain == domain).limit(1))
        if account is None:
            account = Account(
                crm_account_id=f"crm-account:{domain}",
                domain=domain,
                company_name=prospect.company_name or domain,
                hq_country=None,
                employee_count=None,
                revenue_band=None,
                industry=None,
                sub_industry=None,
                tech_stack={},
                security_stack={},
                intent_topics=[],
                territory=None,
                owner_id=actor,
                named_account_flag=False,
                priority_tier=None,
                fit_score=0,
                intent_score=0,
                composite_score=0,
                last_signal_at=None,
                created_at=now,
                updated_at=now,
            )
            session.add(account)
            await session.flush()
        contact = await session.scalar(
            select(Contact)
            .where(Contact.account_id == account.id)
            .where(Contact.email == prospect.email.lower())
            .limit(1)
        )
        if contact is None:
            contact = Contact(
                crm_contact_id=prospect.provider_record_id,
                account_id=account.id,
                full_name=prospect.display_name,
                title=prospect.title,
                seniority=None,
                function="security",
                email=prospect.email.lower(),
                email_status="verified",
                phone=None,
                linkedin_url=None,
                timezone=None,
                persona_type="security_leader",
                buying_role=None,
                last_enriched_at=now,
                do_not_contact_flag=False,
                lawful_basis="legitimate_interest",
                source_vendor="attio" if resolved.attio_access_token else "local-demo-crm",
                source_confidence=80,
                source_url=None,
                source_definition_id=None,
                source_item_ids=[],
                origin_type="manual",
                origin_id=prospect.provider_record_id,
                source_policy_snapshot={"source": "crm_import"},
                review_status="not_required",
                review_reason=None,
                idempotency_key=f"crm-import-contact:{prospect.provider_record_id}",
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(contact)
            await session.flush()
        target_key = f"crm-import-target:{prospect.provider_record_id}"
        target = await session.scalar(
            select(CrmTarget).where(CrmTarget.idempotency_key == target_key)
        )
        if target is None:
            target = CrmTarget(
                review_candidate_id=None,
                review_decision_id=None,
                target_type="contact",
                target_id=contact.id,
                origin_type="manual",
                origin_id=prospect.provider_record_id,
                source_definition_id=None,
                source_item_ids=[],
                status="exported",
                export_status="exported",
                policy_snapshot={"source": "crm_import", **dict(request.policy_snapshot)},
                approval_snapshot={
                    "approved_by": actor,
                    "approval_reason": request.approval_reason,
                },
                idempotency_key=target_key,
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(target)
            await session.flush()
        account_id = account.id
        contact_id = contact.id
        target_id = target.id
    return await create_sequence_enrollment(
        SequenceEnrollmentCreateRequest(
            sequence_id=request.sequence_id,
            crm_target_id=target_id,
            contact_id=contact_id,
            account_id=account_id,
            start_at=request.start_at,
            outreach_approved=True,
            approval_reason=request.approval_reason,
            policy_snapshot=request.policy_snapshot,
        ),
        actor=actor,
        idempotency_key=idempotency_key,
        settings=resolved,
    )


from .common import utcnow  # noqa: E402
from .enrollments import create_sequence_enrollment  # noqa: E402
from .templating import _domain_from_email  # noqa: E402
