from ghostrecon.events.contracts import EventName, new_event


def test_new_event_includes_source_lineage_and_schema_metadata() -> None:
    event = new_event(
        event_name=EventName.SOURCE_ITEM_INGESTED,
        aggregate_type="raw_source_item",
        aggregate_id="raw-1",
        source_service="source-registry",
        source_definition_id="source-1",
        source_item_ids=["raw-1"],
        payload={"canonical_url": "https://example.com/item"},
    )

    payload = event.model_dump(mode="json")

    assert payload["event_name"] == "source.item_ingested"
    assert payload["schema_version"] == "1.0"
    assert payload["producer"] == "source-registry"
    assert payload["source_definition_id"] == "source-1"
    assert payload["source_item_ids"] == ["raw-1"]
    assert "canonical_url" in payload["payload"]
