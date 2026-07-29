from __future__ import annotations

from ghostrecon.models.db import (
    CyberEvent,
    EventParticipant,
)


def event_to_api(event: CyberEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "name": event.name,
        "event_series_key": event.event_series_key,
        "external_id": event.external_id,
        "canonical_url": event.canonical_url,
        "original_start": event.original_start,
        "original_end": event.original_end,
        "source_timezone": event.source_timezone,
        "iana_timezone": event.iana_timezone,
        "timezone_status": event.timezone_status,
        "starts_at_utc": event.starts_at_utc,
        "ends_at_utc": event.ends_at_utc,
        "event_format": event.event_format,
        "venue_name": event.venue_name,
        "street_address": event.street_address,
        "city": event.city,
        "region": event.region,
        "postcode": event.postcode,
        "country": event.country,
        "virtual_url": event.virtual_url,
        "latitude": event.latitude,
        "longitude": event.longitude,
        "geocode_status": event.geocode_status,
        "geocode_provider": event.geocode_provider,
        "geocode_display_name": event.geocode_display_name,
        "geocoded_at": event.geocoded_at,
        "topics": event.topics or [],
        "organizers": event.organizers or [],
        "confidence": event.confidence,
        "canonical_state": event.canonical_state,
        "source_definition_id": event.source_definition_id,
        "source_item_ids": event.source_item_ids or [],
        "version": getattr(event, "version", 1),
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }


def participant_to_api(participant: EventParticipant) -> dict[str, object]:
    return {
        "id": participant.id,
        "cyber_event_id": participant.cyber_event_id,
        "source_definition_id": participant.source_definition_id,
        "source_item_id": participant.source_item_id,
        "source_participant_id": participant.source_participant_id,
        "published_name": participant.published_name,
        "organization": participant.organization,
        "published_role": participant.published_role,
        "participant_type": participant.participant_type,
        "profile_url": participant.profile_url,
        "reuse_state": participant.reuse_state,
        "reuse_evidence": participant.reuse_evidence or {},
        "contact_extraction_allowed": participant.contact_extraction_allowed,
        "crm_export_allowed": participant.crm_export_allowed,
        "resolution_confidence": participant.resolution_confidence,
        "created_at": participant.created_at,
        "updated_at": participant.updated_at,
    }
