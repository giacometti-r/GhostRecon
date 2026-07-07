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


def test_sprint_7_events_are_contract_values() -> None:
    assert EventName.REVIEW_APPROVED.value == "review.approved"
    assert EventName.REVIEW_REJECTED.value == "review.rejected"
    assert EventName.CRM_TARGET_CREATED.value == "crm_target.created"
    assert EventName.SUPPRESSION_CREATED.value == "suppression.created"


def test_sprint_9_crm_export_events_are_contract_values() -> None:
    assert EventName.CRM_EXPORT_BATCH_STARTED.value == "crm_export.batch_started"
    assert EventName.CRM_EXPORT_ITEM_SUCCEEDED.value == "crm_export.item_succeeded"
    assert EventName.CRM_EXPORT_ITEM_FAILED.value == "crm_export.item_failed"
    assert EventName.CRM_EXPORT_BATCH_COMPLETED.value == "crm_export.batch_completed"


def test_sprint_10_sequence_events_are_contract_values() -> None:
    assert EventName.SEQUENCE_ENROLLED.value == "sequence.enrolled"
    assert EventName.SEQUENCE_PAUSED.value == "sequence.paused"
    assert EventName.SEQUENCE_COMPLETED.value == "sequence.completed"
    assert EventName.EMAIL_SENT.value == "email.sent"
    assert EventName.REPLY_RECEIVED.value == "reply.received"
    assert EventName.BOUNCE_RECEIVED.value == "bounce.received"
    assert EventName.UNSUBSCRIBE_RECEIVED.value == "unsubscribe.received"


def test_sprint_11_meeting_events_are_contract_values() -> None:
    assert EventName.MEETING_BOOKED.value == "meeting.booked"
    assert EventName.MEETING_PREP_PACKET_GENERATED.value == "meeting.prep_packet_generated"
    assert EventName.MEETING_OUTCOME_RECORDED.value == "meeting.outcome_recorded"
    assert EventName.MEETING_FOLLOW_UP_TASK_CREATED.value == "meeting.follow_up_task_created"
    assert EventName.CRM_SYNCED.value == "crm.synced"
