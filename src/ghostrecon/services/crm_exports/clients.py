from __future__ import annotations

import hashlib

from ghostrecon.common.config import Settings
from ghostrecon.common.configuration import CrmProvider, assert_adapter_allowed
from ghostrecon.services.crm_attio import (
    AttioCrmClient,
    CrmClient,
    CrmExportPlan,
    CrmExportResult,
    CrmProspect,
    CrmSyncPlan,
)


def _crm_client_for_settings(settings: Settings) -> CrmClient:
    if settings.crm_provider == CrmProvider.ATTIO:
        client: CrmClient = AttioCrmClient(settings)
    elif settings.crm_provider == CrmProvider.LOCAL_DEMO:
        client = LocalDemoCrmClient()
    else:
        raise ValueError("CRM provider is disabled")
    assert_adapter_allowed(settings, client, "crm_provider")
    return client


def crm_client_for_settings(settings: Settings) -> CrmClient:
    return _crm_client_for_settings(settings)


class LocalDemoCrmClient:
    _prospects = [
        CrmProspect(
            provider_record_id="demo-crm-prospect-taylor-ng",
            provider_object="people",
            display_name="Taylor Ng",
            email="taylor.ng@example-industries.com",
            title="VP Security Operations",
            company_name="Example Industries",
            company_domain="example-industries.com",
            source_payload={"provider": "local-demo", "fixture": "sequence-import"},
        ),
        CrmProspect(
            provider_record_id="demo-crm-prospect-morgan-shah",
            provider_object="people",
            display_name="Morgan Shah",
            email="morgan.shah@nimbus-retail.com",
            title="CISO",
            company_name="Nimbus Retail",
            company_domain="nimbus-retail.com",
            source_payload={"provider": "local-demo", "fixture": "sequence-import"},
        ),
        CrmProspect(
            provider_record_id="demo-crm-prospect-riley-kim",
            provider_object="people",
            display_name="Riley Kim",
            email="riley.kim@northstar-health.com",
            title="Director of IT Risk",
            company_name="Northstar Health",
            company_domain="northstar-health.com",
            source_payload={"provider": "local-demo", "fixture": "sequence-import"},
        ),
    ]

    async def export(self, plan: CrmExportPlan) -> CrmExportResult:
        return _demo_result(plan)

    async def sync(self, plan: CrmSyncPlan) -> CrmExportResult:
        return _demo_result(plan)

    async def search_prospects(self, query: str, limit: int = 25) -> list[CrmProspect]:
        normalized = query.lower().strip()
        prospects = self._prospects
        if normalized:
            prospects = [
                prospect
                for prospect in prospects
                if normalized in prospect.display_name.lower()
                or normalized in (prospect.company_name or "").lower()
                or normalized in (prospect.email or "").lower()
                or normalized in (prospect.title or "").lower()
            ]
        return prospects[: max(1, min(limit, 25))]

    async def get_prospect(self, provider_record_id: str) -> CrmProspect | None:
        return next(
            (
                prospect
                for prospect in self._prospects
                if prospect.provider_record_id == provider_record_id
            ),
            None,
        )


def _demo_result(plan: CrmExportPlan | CrmSyncPlan) -> CrmExportResult:
    digest = hashlib.sha256(f"{plan.provider_object}:{plan.stable_match_key}".encode()).hexdigest()
    record_id = f"demo-{plan.provider_object}-{digest[:12]}"
    list_id = f"demo-list-{plan.list_api_slug}" if plan.list_api_slug else None
    entry_id = f"demo-entry-{digest[12:24]}" if plan.list_api_slug else None
    return CrmExportResult(
        provider_record_id=record_id,
        provider_list_id=list_id,
        provider_list_entry_id=entry_id,
        raw_response={"provider": "local-demo", "stable_match_key": plan.stable_match_key},
    )
