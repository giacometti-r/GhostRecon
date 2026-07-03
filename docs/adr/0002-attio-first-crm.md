# ADR 0002 - Attio First CRM Adapter

## Status

Accepted, amended by [ADR 0004](0004-intelligence-first-acquisition.md).

## Context

The platform needs a system of record for approved sales records. Attio was selected first, but future CRM integrations must remain possible. CRM ingestion is not the primary intelligence-acquisition path.

## Decision

Implement `crm-service` around an Attio adapter first and keep all operations behind `CrmClient`. GhostRecon owns intelligence, source lineage, evidence, scoring, governance, and review state; Attio owns approved sales records after export. Avoid leaking Attio-specific object, attribute, or list names into upstream contracts.

CRM export is review-gated, idempotent, and never enrolls a record into outreach. Attio production mapping is sequenced after intelligence ingestion, enrichment, governance, and dashboard review.

## Consequences

- Attio webhooks/imports remain supported compatibility inputs, not the primary acquisition flow.
- Attio production export moves to Sprint 9.
- The Attio adapter maps custom `cyber_events` and `security_incidents` objects plus standard People and Companies records.
- Provider-specific list/object constraints are contained inside the adapter.
- Salesforce, HubSpot, or another provider can implement equivalent mappings behind `CrmClient`.
