from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from ghostrecon.common.config import Settings


class CrmProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class CrmExportPlan:
    target_type: str
    target_id: str
    provider_object: str
    stable_match_key: str
    matching_attribute: str
    values: Mapping[str, Any]
    list_api_slug: str | None = None
    list_entry_values: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CrmSyncPlan:
    sync_type: str
    target_id: str
    provider_object: str
    stable_match_key: str
    matching_attribute: str
    values: Mapping[str, Any]
    list_api_slug: str | None = None
    list_entry_values: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CrmExportResult:
    provider_record_id: str
    provider_list_id: str | None = None
    provider_list_entry_id: str | None = None
    raw_response: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CrmProspect:
    provider_record_id: str
    provider_object: str
    display_name: str
    email: str | None = None
    title: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    source_payload: Mapping[str, Any] = field(default_factory=dict)


class CrmClient(Protocol):
    async def export(self, plan: CrmExportPlan) -> CrmExportResult:
        ...

    async def sync(self, plan: CrmSyncPlan) -> CrmExportResult:
        ...

    async def search_prospects(self, query: str, limit: int = 25) -> list[CrmProspect]:
        ...

    async def get_prospect(self, provider_record_id: str) -> CrmProspect | None:
        ...


class AttioClient:
    """Minimal Attio REST client with token auth and retry-after handling."""

    def __init__(self, settings: Settings) -> None:
        if not settings.attio_access_token:
            raise ValueError("GHOSTRECON_ATTIO_ACCESS_TOKEN is required for Attio API calls")
        self.settings = settings
        self.base_url = str(settings.attio_base_url).rstrip("/")

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.settings.attio_access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                json=json,
                params=params,
                headers=headers,
            )
            if response.status_code == 429:
                retry_after = _optional_int(response.headers.get("Retry-After"))
                raise CrmProviderError(
                    "Attio rate limit exceeded",
                    retryable=True,
                    retry_after_seconds=retry_after,
                )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                retryable = 500 <= response.status_code < 600
                raise CrmProviderError(
                    f"Attio request failed with status {response.status_code}",
                    retryable=retryable,
                ) from exc
            return response.json()


class AttioCrmClient:
    def __init__(self, settings: Settings) -> None:
        self.http = AttioClient(settings)

    async def export(self, plan: CrmExportPlan) -> CrmExportResult:
        return await self._upsert_plan(plan)

    async def sync(self, plan: CrmSyncPlan) -> CrmExportResult:
        return await self._upsert_plan(plan)

    async def search_prospects(self, query: str, limit: int = 25) -> list[CrmProspect]:
        payload = await self.http.request(
            "POST",
            "/v2/objects/records/search",
            json={
                "query": query[:256],
                "objects": ["people", "companies"],
                "request_as": {"type": "workspace"},
                "limit": max(1, min(limit, 25)),
            },
        )
        data = payload.get("data") if isinstance(payload.get("data"), list) else []
        return [_prospect_from_search_result(item) for item in data if isinstance(item, Mapping)]

    async def get_prospect(self, provider_record_id: str) -> CrmProspect | None:
        try:
            payload = await self.http.request(
                "GET",
                f"/v2/objects/people/records/{provider_record_id}",
            )
        except CrmProviderError:
            return None
        return _prospect_from_record_payload(payload, provider_record_id=provider_record_id)

    async def _upsert_plan(self, plan: CrmExportPlan | CrmSyncPlan) -> CrmExportResult:
        record = await self.http.request(
            "PUT",
            f"/v2/objects/{plan.provider_object}/records",
            json={
                "data": {"values": dict(plan.values)},
                "matching_attribute": plan.matching_attribute,
            },
        )
        record_id = _record_id(record)
        list_id = None
        entry_id = None
        raw_response: dict[str, Any] = {"record": record}
        if plan.list_api_slug:
            entry = await self.http.request(
                "PUT",
                f"/v2/lists/{plan.list_api_slug}/entries",
                json={
                    "data": {
                        "parent_record_id": record_id,
                        "parent_object": plan.provider_object,
                        "entry_values": dict(plan.list_entry_values),
                    }
                },
            )
            raw_response["entry"] = entry
            data = _data(entry)
            entry_id_data = data.get("id") if isinstance(data.get("id"), dict) else {}
            if isinstance(entry_id_data, dict):
                list_id = _optional_str(entry_id_data.get("list_id"))
                entry_id = _optional_str(entry_id_data.get("entry_id"))
            list_id = list_id or _optional_str(data.get("list_id"))
            entry_id = entry_id or _optional_str(data.get("entry_id"))
        return CrmExportResult(
            provider_record_id=record_id,
            provider_list_id=list_id,
            provider_list_entry_id=entry_id,
            raw_response=raw_response,
        )


def _data(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, Mapping) else payload


def _record_id(payload: Mapping[str, Any]) -> str:
    data = _data(payload)
    raw_id = data.get("id")
    if isinstance(raw_id, Mapping):
        record_id = raw_id.get("record_id")
        if isinstance(record_id, str) and record_id:
            return record_id
    record_id = data.get("record_id")
    if isinstance(record_id, str) and record_id:
        return record_id
    raise CrmProviderError("Attio response did not include a record ID", retryable=True)


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _prospect_from_search_result(item: Mapping[str, Any]) -> CrmProspect:
    raw_id = item.get("id")
    provider_record_id = ""
    if isinstance(raw_id, Mapping):
        provider_record_id = _optional_str(raw_id.get("record_id")) or ""
    provider_record_id = provider_record_id or _optional_str(item.get("record_id")) or ""
    provider_object = _optional_str(item.get("object_slug")) or "people"
    display_name = _optional_str(item.get("record_text")) or provider_record_id
    return CrmProspect(
        provider_record_id=provider_record_id,
        provider_object=provider_object,
        display_name=display_name,
        source_payload=dict(item),
    )


def _prospect_from_record_payload(
    payload: Mapping[str, Any],
    *,
    provider_record_id: str,
) -> CrmProspect:
    data = _data(payload)
    values = data.get("values") if isinstance(data.get("values"), Mapping) else {}
    name = _attribute_text(values.get("name")) or _attribute_text(values.get("full_name"))
    email = _attribute_email(values.get("email_addresses")) or _attribute_email(values.get("email"))
    company = _attribute_text(values.get("company")) or _attribute_text(
        values.get("primary_company")
    )
    domain = _attribute_domain(values.get("domains")) or _attribute_domain(values.get("domain"))
    title = _attribute_text(values.get("job_title")) or _attribute_text(values.get("title"))
    return CrmProspect(
        provider_record_id=provider_record_id,
        provider_object="people",
        display_name=name or provider_record_id,
        email=email,
        title=title,
        company_name=company,
        company_domain=domain,
        source_payload=dict(data),
    )


def _attribute_text(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("value", "full_name", "first_name", "name"):
            found = _attribute_text(value.get(key))
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _attribute_text(item)
            if found:
                return found
    return None


def _attribute_email(value: object) -> str | None:
    if isinstance(value, str) and "@" in value:
        return value.lower()
    if isinstance(value, Mapping):
        for key in ("email_address", "email", "value"):
            found = _attribute_email(value.get(key))
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _attribute_email(item)
            if found:
                return found
    return None


def _attribute_domain(value: object) -> str | None:
    if isinstance(value, str) and "." in value:
        return value.lower()
    if isinstance(value, Mapping):
        for key in ("domain", "value"):
            found = _attribute_domain(value.get(key))
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _attribute_domain(item)
            if found:
                return found
    return None
