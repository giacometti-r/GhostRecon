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
        status="corroborated",
        title="Example Corp reports ransomware incident",
        incident_group_key="group-1",
        primary_affected_company="Example Corp",
        primary_affected_domain="example.com",
        affected_companies=["Example Corp"],
        affected_domains=["example.com"],
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
        evidence_urls=["https://news.example/breach"],
        corroboration_method="analyst_decision",
        analyst_decision_ref=None,
        canonical_state="canonical",
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        version=1,
        created_at=now,
        updated_at=now,
    )


def _watch_target():
    now = datetime(2026, 7, 3, tzinfo=UTC)
    return SimpleNamespace(
        id="watch-1",
        target_type="company",
        canonical_target_key="example-corp",
        display_name="Example Corp",
        query_config={"incident_id": "incident-1", "domains": ["example.com"]},
        enabled=True,
        monitoring_status="not_run",
        last_monitored_at=None,
        next_monitoring_at=None,
        monitoring_error=None,
        monitoring_summary={},
        owner="analyst@example.com",
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
        assert kwargs["version"] == 1
        assert kwargs["actor"] == "analyst@example.com"
        return _watch_target()

    async def fake_get_watch_target(watch_target_id, **kwargs):
        assert watch_target_id == "watch-1"
        return _watch_target()

    async def fake_monitor_watch_targets(**kwargs):
        return {"checked": 1, "failed": 0, "provider": "local_demo"}

    monkeypatch.setattr(routers.incidents, "list_incidents", fake_list_incidents)
    monkeypatch.setattr(routers.incidents, "get_incident", fake_get_incident)
    monkeypatch.setattr(routers.incidents, "get_watch_target", fake_get_watch_target)
    monkeypatch.setattr(routers.incidents, "monitor_watch_targets", fake_monitor_watch_targets)
    monkeypatch.setattr(
        routers.incidents, "promote_incident_to_watchlist", fake_promote_incident_to_watchlist
    )

    app = build_app(Settings(service_name="incident-intelligence-service"))
    client = TestClient(app)

    incidents = client.get("/v1/intelligence/incidents").json()["incidents"]
    watch = client.post(
        "/v1/intelligence/incidents/incident-1/promote-to-watchlist",
        headers={"Idempotency-Key": "idem-1", "X-Actor": "analyst@example.com"},
        json={"version": 1},
    ).json()
    watch_detail = client.get("/v1/intelligence/watch-targets/watch-1").json()
    monitoring = client.post("/v1/intelligence/watch-targets/monitor").json()

    assert incidents[0]["status"] == "corroborated"
    assert incidents[0]["affected_companies"] == ["Example Corp"]
    assert incidents[0]["primary_affected_company"] == "Example Corp"
    assert incidents[0]["evidence_urls"] == ["https://news.example/breach"]
    assert incidents[0]["version"] == 1
    assert watch["origin_incident_id"] == "incident-1"
    assert watch["target_type"] == "company"
    assert watch["owner"] == "analyst@example.com"
    assert watch_detail["monitoring_status"] == "not_run"
    assert monitoring["checked"] == 1


def test_manual_incident_route_exposes_version(monkeypatch) -> None:
    async def fake_create_manual_incident(request, **kwargs):
        assert request.title == "Manual incident"
        assert kwargs["actor"] == "analyst@example.com"
        return [_incident()]

    monkeypatch.setattr(routers.incidents, "create_manual_incident", fake_create_manual_incident)

    client = TestClient(build_app(Settings(service_name="incident-intelligence-service")))
    response = client.post(
        "/v1/intelligence/incidents/manual",
        headers={"Idempotency-Key": "manual-incident-1", "X-Actor": "analyst@example.com"},
        json={"title": "Manual incident", "affected_companies": ["Example Corp"]},
    )

    assert response.status_code == 200
    assert response.json()["incidents"][0]["version"] == 1
