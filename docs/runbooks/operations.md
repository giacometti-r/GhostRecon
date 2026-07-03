# Operations Runbook

This runbook covers the implemented platform baseline, Sprint 3 source registry foundation, Sprint 4 event intelligence runtime, Sprint 5 incident intelligence/watchlist runtime, and the remaining intelligence-first target state for later sprints.

## Health and Freshness

- `/healthz`: process liveness.
- `/readyz`: dependency readiness.
- `/metrics`: Prometheus metrics.
- `GET /v1/intelligence/sources/health`: source checkpoint, last-success, lag, error, freshness, enabled/degraded, and policy state for registered sources.
- Dashboard responses must expose `generated_at`, data-window end, and stale/degraded markers.

Do not equate process health with data freshness. A service can be live while its sources or reporting projections are stale.

## Common Incidents

### Stale or Failing Event Source

1. Identify the affected `SourceDefinition`, adapter, last successful checkpoint, and freshness objective.
2. Check upstream status, robots/rate-limit response, conditional-request state, and parser errors.
3. Disable only the failing source if repeated malformed content threatens queue health.
4. Replay from the last durable checkpoint with the same source-item idempotency keys.
5. Verify duplicate rate, timezone normalization, lineage, and permitted-excerpt policy before clearing degraded state.

### GDELT, RSS, or Advisory Discovery Outage

1. Confirm whether the failure is provider-specific, query-specific, or a shared network/queue issue.
2. Continue independent feeds and watch queries; do not mark incidents corroborated solely because one provider recovered.
3. Respect provider rate limits and use capped backoff with jitter.
4. On recovery, replay the missed time window and verify article canonical-URL/content-hash deduplication.
5. Keep the dashboard stale/degraded indicator active until the replay watermark catches up.

### Duplicate Event or Incident Cases

1. Compare canonical URLs, source hashes, event-series/date/location keys, affected-company resolution, evidence URLs, and incident time windows.
2. Merge through an audited canonicalization action; do not delete source lineage.
3. Redirect watch targets, review candidates, and pending export items to the surviving canonical ID.
4. Rebuild reporting projections and confirm subsequent coverage joins the canonical case.

### Incident Corroboration Dispute

1. Keep the incident in `candidate` state and block CRM export.
2. Review authoritative disclosures, source independence, affected-company resolution, translation provenance, and analyst notes.
3. Corroborate only through an authoritative disclosure, multiple independent sources, or an audited analyst decision.
4. Reject false positives with a reason code; retain evidence and the decision audit according to policy.

### Participant Permission Violation

1. Set the source/item reuse state to `unknown` or `prohibited` immediately.
2. Block new participant contact extraction and CRM export candidates.
3. Quarantine affected unapproved candidates and cancel pending export items that have not executed.
4. Ask governance owners to determine retention/deletion actions for previously derived data.
5. Audit the policy change, affected records, and remediation.

### Review Queue Backlog

1. Check queue age by candidate type, risk, source permission, and analyst assignment.
2. Scale read projections/workers if lag is technical; do not bypass review to reduce backlog.
3. Use bounded bulk actions only for homogeneous candidates with the same displayed policy/evidence context.
4. Preserve per-candidate decision, actor, reason, policy version, and idempotency key.

### CRM Export Rate Limit or Partial Failure

1. Pause only the affected provider/workspace queue and honor `Retry-After`.
2. Inspect `CrmExportBatch` and each `CrmExportItem`; never restart the whole batch blindly.
3. Retry failed items with their original idempotency keys and expected stable identifiers.
4. Upsert People and Companies before list entries; verify custom-object dependencies before dependent writes.
5. Reconcile GhostRecon IDs, CRM record IDs, list-entry IDs, and source-lineage fields.
6. Surface unresolved items in the dashboard. Export success must not create sequence enrollment.

### Dashboard or Reporting Data Is Stale

1. Compare source watermarks, outbox lag, reporting projection lag, and response `generated_at` values.
2. Keep mutating actions blocked if their evidence or policy projection is stale.
3. Rebuild only the affected read model, then compare counts and canonical IDs with source tables.
4. Clear stale state only after lag returns inside the documented objective.

### Attio Webhook Delivery Failures

Attio webhook intake is a compatibility path, not primary acquisition.

1. Check `ingestion-service` logs for signature failures and 5xx responses.
2. Confirm `GHOSTRECON_ATTIO_WEBHOOK_SECRET`.
3. Check queue depth and worker availability.
4. Replay only after checking idempotency and canonical-record state.

### Crawler Backlog

1. Check Redis queue depth for enrichment workers.
2. Scale `enrichment-service` workers horizontally.
3. Verify target domains are allowlisted and robots policy is respected.
4. Do not disable robots handling in production without legal approval.

### Email Verification Failures

1. Check the `email-verifier` service and its Redis cache dependency.
2. Retry batch jobs after DNS/network recovery with capped backoff.
3. Leave candidates pending; do not promote ambiguous or unverifiable addresses.

### Suppression or Governance Errors

1. Pause CRM export mutations and sequence enrollment for affected candidates.
2. Check `governance-service` logs, source-policy state, approval projections, and suppression tables.
3. Re-run policy and suppression reconciliation.
4. Audit any affected export or outbound action before replaying.

## Escalation Evidence

Every escalation should include correlation ID, service/source ID, canonical entity ID, fetch or outbox watermark, idempotency key, policy version, audit ID, timestamps in UTC, and the operator action already attempted. Do not attach unlicensed article bodies or prohibited personal data.
