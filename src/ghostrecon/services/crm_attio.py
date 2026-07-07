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
class CrmExportResult:
    provider_record_id: str
    provider_list_id: str | None = None
    provider_list_entry_id: str | None = None
    raw_response: Mapping[str, Any] = field(default_factory=dict)


class CrmClient(Protocol):
    async def export(self, plan: CrmExportPlan) -> CrmExportResult:
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
