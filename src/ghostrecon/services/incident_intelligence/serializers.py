from __future__ import annotations

from ghostrecon.models.db import (
    SecurityIncident,
    WatchTarget,
)


def incident_to_api(incident: SecurityIncident) -> dict[str, object]:
    return {
        "id": incident.id,
        "status": incident.status,
        "title": incident.title,
        "incident_group_key": incident.incident_group_key,
        "primary_affected_company": incident.primary_affected_company,
        "primary_affected_domain": incident.primary_affected_domain,
        "affected_companies": incident.affected_companies or [],
        "affected_domains": incident.affected_domains or [],
        "incident_type": incident.incident_type,
        "attack_vector": incident.attack_vector,
        "first_observed_at": incident.first_observed_at,
        "last_observed_at": incident.last_observed_at,
        "geography": incident.geography or [],
        "languages": incident.languages or [],
        "confidence": incident.confidence,
        "evidence_article_ids": incident.evidence_article_ids or [],
        "evidence_source_item_ids": incident.evidence_source_item_ids or [],
        "evidence_families": incident.evidence_families or [],
        "evidence_urls": incident.evidence_urls or [],
        "corroboration_method": incident.corroboration_method,
        "analyst_decision_ref": incident.analyst_decision_ref,
        "canonical_state": incident.canonical_state,
        "source_definition_id": incident.source_definition_id,
        "source_item_ids": incident.source_item_ids or [],
        "version": getattr(incident, "version", 1),
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
    }


def watch_target_to_api(target: WatchTarget) -> dict[str, object]:
    return {
        "id": target.id,
        "target_type": target.target_type,
        "canonical_target_key": target.canonical_target_key,
        "display_name": target.display_name,
        "query_config": target.query_config or {},
        "enabled": target.enabled,
        "monitoring_enabled": target.enabled,
        "monitoring_status": target.monitoring_status,
        "last_monitored_at": target.last_monitored_at,
        "next_monitoring_at": target.next_monitoring_at,
        "monitoring_error": target.monitoring_error,
        "monitoring_summary": target.monitoring_summary or {},
        "owner": target.owner,
        "origin_incident_id": target.origin_incident_id,
        "created_by": target.created_by,
        "version": target.version,
        "created_at": target.created_at,
        "updated_at": target.updated_at,
    }
