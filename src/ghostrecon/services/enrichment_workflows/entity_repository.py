from __future__ import annotations

from sqlalchemy import select

from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    EntityResolutionCreate,
)
from ghostrecon.models.db import (
    EntityResolutionCase,
)


class EntityResolutionRepositoryMixin:
    async def create_entity_resolution(
        self, payload: EntityResolutionCreate, idempotency_key: str
    ) -> EntityResolutionCase:
        existing = await self.session.scalar(
            select(EntityResolutionCase).where(
                EntityResolutionCase.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            return existing

        domain = normalize_domain(payload.domain)
        case = EntityResolutionCase(
            origin_type=payload.origin_type,
            origin_id=payload.origin_id,
            entity_kind=payload.entity_kind,
            input_name=payload.organization_name,
            input_domain=domain,
            source_definition_id=payload.source_definition_id,
            source_item_ids=list(payload.source_item_ids),
            policy_snapshot=payload.policy_snapshot,
            idempotency_key=idempotency_key,
        )
        self.session.add(case)
        await self.session.flush()

        if not payload.source_definition_id or not payload.source_item_ids:
            case.status = "blocked"
            case.review_reason = "missing_source_lineage"
            await self._request_review(
                candidate_type="entity_resolution",
                target_type="entity_resolution_case",
                target_id=case.id,
                origin_type=case.origin_type,
                origin_id=case.origin_id,
                source_definition_id=case.source_definition_id,
                source_item_ids=case.source_item_ids,
                reason_code="missing_source_lineage",
                reason="Entity resolution input did not include source lineage.",
                evidence_summary=entity_resolution_to_api(case),
                policy_snapshot=case.policy_snapshot,
            )
            return case

        matches = await self._find_account_matches(domain, payload.organization_name)
        case.alternatives = [_account_summary(account) for account in matches]
        if len(matches) == 1:
            account = matches[0]
            case.status = "resolved"
            case.confidence = 100 if domain else 90
            case.resolved_account_id = account.id
            case.resolved_name = account.company_name
            case.resolved_domain = account.domain
            self._enqueue_event(
                new_event(
                    event_name=EventName.ACCOUNT_ENRICHED,
                    aggregate_type="account",
                    aggregate_id=account.id,
                    source_service=ENRICHMENT_SERVICE_NAME,
                    source_definition_id=case.source_definition_id,
                    source_item_ids=[str(item) for item in case.source_item_ids],
                    payload={
                        "account_id": account.id,
                        "domain": account.domain,
                        "origin_type": case.origin_type,
                        "origin_id": case.origin_id,
                        "resolution_case_id": case.id,
                    },
                    idempotency_key=f"account.enriched:{case.id}:{account.id}",
                )
            )
        else:
            case.status = "ambiguous" if len(matches) > 1 else "needs_review"
            case.confidence = 60 if matches else 0
            case.review_reason = "multiple_account_matches" if matches else "no_account_match"
            await self._request_review(
                candidate_type="entity_resolution",
                target_type="entity_resolution_case",
                target_id=case.id,
                origin_type=case.origin_type,
                origin_id=case.origin_id,
                source_definition_id=case.source_definition_id,
                source_item_ids=case.source_item_ids,
                reason_code=case.review_reason,
                reason="Entity resolution requires analyst review.",
                evidence_summary=entity_resolution_to_api(case),
                policy_snapshot=case.policy_snapshot,
            )
        return case

    async def list_entity_resolutions(
        self, *, status: str | None, origin_type: str | None, limit: int
    ) -> list[EntityResolutionCase]:
        stmt = (
            select(EntityResolutionCase)
            .order_by(EntityResolutionCase.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(EntityResolutionCase.status == status)
        if origin_type:
            stmt = stmt.where(EntityResolutionCase.origin_type == origin_type)
        result = await self.session.execute(stmt)
        return list(result.scalars())


from .policy import ENRICHMENT_SERVICE_NAME, normalize_domain  # noqa: E402
from .serializers import _account_summary, entity_resolution_to_api  # noqa: E402
