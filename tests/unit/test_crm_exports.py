from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from ghostrecon.common.config import Settings
from ghostrecon.models.api import (
    CrmExportBatchOut,
    CrmExportItemOut,
)
from ghostrecon.service_apps import routers
from ghostrecon.service_apps.factory import build_app
from ghostrecon.services.crm_attio import (
    AttioClient,
    AttioCrmClient,
    CrmExportPlan,
    CrmProviderError,
    CrmSyncPlan,
)
from ghostrecon.services.crm_exports import (
    LocalDemoCrmClient,
    _crm_client_for_settings,
    _require_exportable_targets,
    selection_hash,
)

NOW = datetime(2026, 7, 7, tzinfo=UTC)


def _item(status: str = "succeeded") -> CrmExportItemOut:
    return CrmExportItemOut(
        id="item-1",
        batch_id="batch-1",
        crm_target_id="crm-target-1",
        target_type="security_incident",
        target_id="incident-1",
        operation="upsert_record",
        provider_object="security_incidents",
        provider_record_id="attio-record-1" if status == "succeeded" else None,
        provider_list_id="list-1" if status == "succeeded" else None,
        provider_list_entry_id="entry-1" if status == "succeeded" else None,
        stable_match_key="ghostrecon_incident:incident-1",
        status=status,
        attempt_count=1,
        last_error=None if status == "succeeded" else "rate limited",
        retry_after_seconds=30 if status == "failed_retryable" else None,
        reconciliation_state="not_required",
        created_at=NOW,
        updated_at=NOW,
    )


def _batch(status: str = "succeeded", item_status: str = "succeeded") -> CrmExportBatchOut:
    return CrmExportBatchOut(
        id="batch-1",
        provider="attio",
        workspace_id="workspace-1",
        requested_by="analyst@example.com",
        status=status,
        crm_target_ids=["crm-target-1"],
        selection_hash=selection_hash(["crm-target-1"]),
        idempotency_key="idem-export",
        counts={"total": 1, item_status: 1},
        reconciliation_summary={"pending_reconciliation": 0},
        started_at=NOW,
        completed_at=NOW,
        created_at=NOW,
        updated_at=NOW,
        items=[_item(item_status)],
    )


def test_crm_export_routes_start_detail_and_retry(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def fake_start(request, **kwargs):
        seen["start_ids"] = request.crm_target_ids
        seen["actor"] = kwargs["actor"]
        seen["idempotency_key"] = kwargs["idempotency_key"]
        return _batch()

    async def fake_get(*args, **kwargs):
        return _batch()

    async def fake_retry(*args, **kwargs):
        seen["retry_key"] = kwargs["idempotency_key"]
        return _batch("partial", "failed_retryable")

    monkeypatch.setattr(routers.crm, "start_crm_export", fake_start)
    monkeypatch.setattr(routers.crm, "get_crm_export_batch", fake_get)
    monkeypatch.setattr(routers.crm, "retry_failed_crm_export_items", fake_retry)

    client = TestClient(build_app(Settings(service_name="crm-service")))
    headers = {"Idempotency-Key": "idem-export", "X-Test-Metadata": "analyst@example.com"}
    started = client.post(
        "/v1/crm/exports",
        headers=headers,
        json={"crm_target_ids": ["crm-target-1"], "workspace_id": "workspace-1"},
    ).json()
    detail = client.get("/v1/crm/exports/batch-1").json()
    retried = client.post(
        "/v1/crm/exports/batch-1/retry-failed",
        headers={"Idempotency-Key": "idem-retry", "X-Test-Metadata": "analyst@example.com"},
        json={"item_ids": ["item-1"]},
    ).json()

    assert started["status"] == "succeeded"
    assert detail["items"][0]["provider_record_id"] == "attio-record-1"
    assert retried["status"] == "partial"
    assert retried["items"][0]["retry_after_seconds"] == 30
    assert seen == {
        "start_ids": ["crm-target-1"],
        "actor": "Local development administrator",
        "idempotency_key": "idem-export",
        "retry_key": "idem-retry",
    }


def test_exportable_target_validation_requires_current_approved_targets() -> None:
    exportable = SimpleNamespace(
        id="crm-target-1",
        status="pending_export",
        export_status="not_exported",
    )
    exported = SimpleNamespace(
        id="crm-target-2",
        status="exported",
        export_status="exported",
    )

    _require_exportable_targets(["crm-target-1"], {"crm-target-1": exportable})
    with pytest.raises(ValueError, match="not pending export"):
        _require_exportable_targets(["crm-target-2"], {"crm-target-2": exported})


def test_selection_hash_is_order_independent() -> None:
    assert selection_hash(["b", "a"]) == selection_hash(["a", "b"])


def test_local_demo_crm_client_is_used_without_attio_token() -> None:
    client = _crm_client_for_settings(Settings(profile="local", crm_provider="local_demo"))

    assert isinstance(client, LocalDemoCrmClient)


@pytest.mark.asyncio
async def test_local_demo_crm_client_returns_fake_prospects() -> None:
    client = LocalDemoCrmClient()

    prospects = await client.search_prospects("taylor", limit=5)
    prospect = await client.get_prospect("demo-crm-prospect-taylor-ng")

    assert prospects[0].display_name == "Taylor Ng"
    assert prospects[0].email == "taylor.ng@example-industries.com"
    assert prospect is not None
    assert prospect.company_domain == "example-industries.com"


@pytest.mark.asyncio
async def test_attio_crm_client_searches_people_and_companies() -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    class FakeHttp:
        async def request(self, method, path, *, json=None, params=None):
            _ = params
            calls.append((method, path, json))
            return {
                "data": [
                    {
                        "id": {"record_id": "attio-person-1"},
                        "record_text": "Taylor Ng",
                        "object_slug": "people",
                    }
                ]
            }

    client = AttioCrmClient.__new__(AttioCrmClient)
    client.http = FakeHttp()

    prospects = await client.search_prospects("Taylor", limit=3)

    assert prospects[0].provider_record_id == "attio-person-1"
    assert calls == [
        (
            "POST",
            "/v2/objects/records/search",
            {
                "query": "Taylor",
                "objects": ["people", "companies"],
                "request_as": {"type": "workspace"},
                "limit": 3,
            },
        )
    ]


@pytest.mark.asyncio
async def test_attio_crm_client_upserts_record_and_list_entry() -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    class FakeHttp:
        async def request(self, method, path, *, json=None, params=None):
            _ = params
            calls.append((method, path, json))
            if path.endswith("/records"):
                return {"data": {"id": {"record_id": "attio-record-1"}}}
            return {"data": {"id": {"list_id": "attio-list-1", "entry_id": "attio-entry-1"}}}

    client = AttioCrmClient.__new__(AttioCrmClient)
    client.http = FakeHttp()
    result = await client.export(
        CrmExportPlan(
            target_type="security_incident",
            target_id="incident-1",
            provider_object="security_incidents",
            stable_match_key="ghostrecon_incident:incident-1",
            matching_attribute="ghostrecon_id",
            values={"ghostrecon_id": "incident-1", "title": "Example incident"},
            list_api_slug="ghostrecon-security-incidents",
            list_entry_values={"export_status": "approved"},
        )
    )

    assert result.provider_record_id == "attio-record-1"
    assert result.provider_list_entry_id == "attio-entry-1"
    assert calls[0][0] == "PUT"
    assert calls[0][1] == "/v2/objects/security_incidents/records"
    assert calls[0][2]["matching_attribute"] == "ghostrecon_id"  # type: ignore[index]
    assert calls[1][1] == "/v2/lists/ghostrecon-security-incidents/entries"


@pytest.mark.asyncio
async def test_attio_crm_client_syncs_meeting_handoff_plan() -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    class FakeHttp:
        async def request(self, method, path, *, json=None, params=None):
            _ = params
            calls.append((method, path, json))
            if path.endswith("/records"):
                return {"data": {"id": {"record_id": "attio-meeting-1"}}}
            return {"data": {"id": {"list_id": "attio-list-1", "entry_id": "attio-entry-1"}}}

    client = AttioCrmClient.__new__(AttioCrmClient)
    client.http = FakeHttp()
    result = await client.sync(
        CrmSyncPlan(
            sync_type="meeting_handoff",
            target_id="meeting-1",
            provider_object="meeting_handoffs",
            stable_match_key="ghostrecon_meeting:meeting-1",
            matching_attribute="ghostrecon_id",
            values={"ghostrecon_id": "meeting-1", "subject": "Security discovery"},
            list_api_slug="ghostrecon-meetings",
            list_entry_values={"meeting_status": "completed"},
        )
    )

    assert result.provider_record_id == "attio-meeting-1"
    assert result.provider_list_entry_id == "attio-entry-1"
    assert calls[0][1] == "/v2/objects/meeting_handoffs/records"
    assert calls[1][1] == "/v2/lists/ghostrecon-meetings/entries"


@pytest.mark.asyncio
@respx.mock
async def test_attio_client_marks_rate_limits_retryable() -> None:
    respx.get("https://api.attio.com/v2/test").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "12"})
    )
    client = AttioClient(
        Settings(attio_access_token="unit-test-token", attio_base_url="https://api.attio.com")  # noqa: S106
    )

    with pytest.raises(CrmProviderError) as exc:
        await client.request("GET", "/v2/test")

    assert exc.value.retryable is True
    assert exc.value.retry_after_seconds == 12
