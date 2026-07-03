from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from ghostrecon.common.config import Settings
from ghostrecon.service_apps import routers
from ghostrecon.service_apps.factory import build_app


def _incident():
    now = datetime(2026, 7, 3, tzinfo=UTC)
    return SimpleNamespace(
        id="incident-1",
        status="candidate",
        title="Example Corp reports ransomware incident",
        affected_companies=["Example Corp"],
        affected_domains=[],
        incident_type="ransomware",
        attack_vector="ransomware",
        first_observed_at=now,
        last_observed_at=now,
        geography=["US"],
        languages=["English"],
        confidence=75,
        evidence_article_ids=["article-1"],
        evidence_source_item_ids=["raw-1"],
        evidence_families=["news-example"],
        corroboration_method="none",
        analyst_decision_ref=None,
        canonical_state="canonical",
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        created_at=now,
        updated_at=now,
    )


def _watch_target():
    now = datetime(2026, 7, 3, tzinfo=UTC)
    return SimpleNamespace(
        id="watch-1",
        target_type="incident",
        canonical_target_key="incident-1",
        display_name="Example Corp reports ransomware incident",
        query_config={"incident_id": "incident-1"},
        enabled=True,
        owner=None,
        origin_incident_id="incident-1",
        created_by="analyst@example.com",
        version=1,
        created_at=now,
        updated_at=now,
    )


def test_incident_routes_return_incidents_and_promoted_watch_targets(monkeypatch) -> None:
    async def fake_list_incidents(**kwargs):
        return [_incident()]

    async def fake_get_incident(incident_id, settings=None):
        return _incident()

    async def fake_promote_incident_to_watchlist(incident_id, **kwargs):
        return _watch_target()

    monkeypatch.setattr(routers, "list_incidents", fake_list_incidents)
    monkeypatch.setattr(routers, "get_incident", fake_get_incident)
    monkeypatch.setattr(
        routers, "promote_incident_to_watchlist", fake_promote_incident_to_watchlist
    )

    app = build_app(Settings(service_name="incident-intelligence-service"))
    client = TestClient(app)

    incidents = client.get("/v1/intelligence/incidents").json()["incidents"]
    watch = client.post(
        "/v1/intelligence/incidents/incident-1/promote-to-watchlist",
        headers={"Idempotency-Key": "idem-1", "X-Actor": "analyst@example.com"},
    ).json()

    assert incidents[0]["status"] == "candidate"
    assert incidents[0]["affected_companies"] == ["Example Corp"]
    assert watch["origin_incident_id"] == "incident-1"
    assert watch["target_type"] == "incident"
