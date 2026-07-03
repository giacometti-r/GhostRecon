# ADR 0004 - Intelligence-First Acquisition and Review-Gated CRM Activation

## Status

Accepted.

## Context

The original implementation direction presented CRM ingestion as the primary source of accounts and contacts. The product now needs global cybersecurity-event discovery, permitted published-participant discovery, cyber-incident monitoring, affected-company identification, and operator-managed watchlists. CRM-first acquisition cannot represent source permissions, multilingual evidence, incident corroboration, or pre-CRM analyst review cleanly.

`deep-research-report.md` is retained as historical research and is not rewritten by this decision.

## Decision

Adopt this primary flow:

external event/news sources → normalization and deduplication → company/contact enrichment → scoring and governance → analyst review → CRM export → reporting.

Add two service boundaries:

- `event-intelligence-service` owns global event, event-series, and permitted published-participant discovery.
- `incident-intelligence-service` owns global article discovery, incident candidates, affected-company identification, corroboration evidence, and watchlists.

Build intelligence dashboards and review queues in the existing `console-service`, backed by `reporting-service`. Do not create a separate dashboard service.

Attio remains the first CRM and the authority for approved sales records. `crm-service` exports only analyst-approved targets through provider-neutral `CrmClient` batches. Export does not imply or trigger outreach enrollment.

## Policy Boundaries

- Store source metadata, hashes, URLs, and permitted excerpts rather than unlicensed full articles.
- Participant extraction and CRM eligibility require explicit source permission for reuse.
- Incident contacts must be public business contacts in security, IT, risk, or communications roles.
- Breached personal data is prohibited.
- Incidents begin as `candidate` and become `corroborated` only through authoritative disclosure, multiple independent sources, or an audited analyst decision.
- A global incident may be promoted into a watchlist without replacing or severing the originating incident record.

## Consequences

- Sprints 0–2 remain valid; future sequencing changes to intelligence acquisition before CRM production export.
- New canonical entities, contracts, source-health controls, evidence rules, and review APIs are required.
- `ingestion-service` remains useful for CRM webhooks and imports but no longer defines the acquisition architecture.
- CRM provider constraints stay isolated inside `CrmClient` adapters.
- Source outages, stale feeds, false positives, policy ambiguity, partial exports, and reconciliation become dashboard-visible operating states.
- Runtime implementation follows the revised sprint roadmap; this ADR and its linked specifications define the target state.
