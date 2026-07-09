# Operations Runbook

This runbook covers the implemented platform baseline, Sprint 3 source registry foundation, Sprint 4 event intelligence runtime, Sprint 5 incident intelligence/watchlist runtime, Sprint 9 CRM export runtime, Sprint 10 sequencing runtime, Sprint 11 Google Calendar meeting handoff runtime, Sprint 12 Dash console runtime, Sprint 17 event dashboard workflow, Sprint 18 incident governance/watchlist workflow, and the remaining intelligence-first target state for later sprints.

## Health and Freshness

- `/healthz`: process liveness.
- `/readyz`: dependency readiness.
- `/metrics`: Prometheus metrics.
- `GET /v1/intelligence/sources/health`: source checkpoint, last-success, lag, error, freshness, enabled/degraded, and policy state for registered sources.
- Dashboard responses must expose `generated_at`, data-window end, and stale/degraded markers.
- Meeting reporting responses expose meeting watermarks and CRM sync failure state; process health does not prove Google Calendar or Attio meeting sync is current.
- The Dash console can be live while gateway, reporting, or owner-service callbacks are degraded. Check console process health separately from dashboard data freshness and action failures.

Do not equate process health with data freshness. A service can be live while its sources or reporting projections are stale.

## Common Incidents

### Stale or Failing Event Source

1. Identify the affected `SourceDefinition`, adapter, last successful checkpoint, and freshness objective.
2. Check upstream status, robots/rate-limit response, conditional-request state, and parser errors.
3. Disable only the failing source if repeated malformed content threatens queue health.
4. Replay from the last durable checkpoint with the same source-item idempotency keys.
5. Verify duplicate rate, timezone normalization, lineage, and permitted-excerpt policy before clearing degraded state.

### Event Geocoding Failure

1. Check whether `GHOSTRECON_GEOCODER_PROVIDER` is `local_demo`, `nominatim`, or `disabled`.
2. For Nominatim-compatible providers, confirm `GHOSTRECON_NOMINATIM_BASE_URL`, identifying `GHOSTRECON_NOMINATIM_USER_AGENT`, network reachability, and low request rate.
3. Failed or no-result geocoding should leave events created with `geocode_status=failed` or `not_found`; do not delete manually entered events solely because coordinates are missing.
4. Correct structured address fields, then patch the event with the current optimistic version to retry geocoding.

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

1. Keep the incident in `candidate` state and block CRM export/watch promotion until corroborated.
2. Review authoritative disclosures, source independence, affected-company resolution, translation provenance, and analyst notes.
3. Corroborate only through an authoritative disclosure, multiple independent sources, or an audited analyst decision.
4. Use `POST /v1/governance/incidents/{incident_id}/revert` with the current version if a corroborated incident must return to candidate state.
5. Reject false positives with a reason code; retain evidence and the decision audit according to policy.

### Incident Watch Promotion Failure

1. Confirm the incident is `corroborated`, the supplied optimistic version matches, and `primary_affected_company` is populated.
2. Promotion creates or returns a company watch target owned by the acting user. Do not create incident-level watch targets as a workaround for missing company context.
3. If a multi-company attack is involved, promote the company-specific incident row for the intended affected company.
4. Re-run reporting after promotion if the dashboard row does not disappear from the current table view.

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

### Dash Console Outage or Callback Failures

1. Check `console-service` `/healthz`, `/readyz`, and pod/container logs separately from `gateway-service` and `reporting-service`.
2. Confirm `GHOSTRECON_GATEWAY_BASE_URL`, `GHOSTRECON_CONSOLE_REQUEST_TIMEOUT_SECONDS`, and any ingress/proxy headers for `X-Actor` and `X-Operator-Role`.
3. If pages render but actions fail, inspect the owning service route, status code, idempotency key, actor, role, optimistic version, and audit/correlation ID.
4. If participant enrichment buttons do not disable after queueing, inspect `/v1/enrichment/contact-candidates?origin_type=event_participant&origin_id=...` for durable queue state.
5. If reporting callbacks time out, keep the stale/degraded banner visible and avoid bypassing the console by mutating canonical tables.
6. Source-health pause/replay/acknowledge controls are intentionally read-only until owning source-operations APIs are implemented.

### Attio API Export Failures

Attio interaction runs through the CRM service's Attio API adapter.

1. Check `crm-service` logs for Attio API status codes and retryable provider errors.
2. Confirm `GHOSTRECON_ATTIO_ACCESS_TOKEN`, `GHOSTRECON_ATTIO_BASE_URL`, and Attio list slug settings.
3. Check CRM export batch/item state and retry failed retryable items through the CRM export retry API.
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

### Sequence SMTP Outage

1. Check `sequencing-service` logs, `GHOSTRECON_SMTP_*` configuration, provider status, and network reachability.
2. Pause only affected sender/channel queues when failures are provider-specific.
3. Leave failed outbound emails in retryable state with retry metadata; do not create replacement enrollments.
4. After recovery, process due sequence steps and confirm provider message IDs are recorded once per outbound email.

### Sequence IMAP Outage

1. Check `GHOSTRECON_IMAP_*` configuration, mailbox permissions, and provider status.
2. Continue suppression-before-send checks; do not disable safety gates because reply processing is delayed.
3. Poll missed messages after recovery and verify replies, bounces, and unsubscribes are idempotently recorded.
4. Keep dashboard state degraded until inbound polling catches up.

### Bounce Spike

1. Pause affected sender, domain, or sequence enrollments based on the bounce pattern.
2. Inspect recent `InboundEmailEvent` and `OutboundEmail` rows for provider message IDs, domains, and templates.
3. Verify email verification evidence and source lineage before resuming.
4. Audit any resumed enrollment with the reason for recovery.

### Unsubscribe or Suppression-Before-Send Failure

1. Confirm the unsubscribe created an active suppression row and `SequenceSuppressionEvent` linkage.
2. Suppress or pause active enrollments for the address/domain; never retry sends for suppressed contacts.
3. Re-run due-step processing only after suppression reconciliation is complete.
4. Preserve inbound event payload metadata but do not store prohibited personal data beyond the suppression scope.

### Google Calendar Auth Failure

1. Check `meeting-handoff-service` logs for token errors from `oauth2.googleapis.com`.
2. Confirm `GHOSTRECON_GOOGLE_CALENDAR_ID`, `GHOSTRECON_GOOGLE_CLIENT_EMAIL`, `GHOSTRECON_GOOGLE_PRIVATE_KEY`, and optional `GHOSTRECON_GOOGLE_DELEGATED_SUBJECT`.
3. Verify the service account has calendar access or Workspace domain-wide delegation for the delegated subject.
4. Do not retry by creating duplicate meetings manually; use the same meeting idempotency key once credentials are corrected.
5. Keep meeting reporting degraded until booking and availability checks succeed again.

### Google Calendar Rate Limit or Provider Outage

1. Inspect the provider response and honor any `Retry-After` value.
2. Pause only meeting creation/cancel operations that target the affected calendar.
3. Do not bypass suppression checks or create replacement meetings in another calendar without an audit reason.
4. Retry failed booking or cancellation with the original idempotency key after the provider window clears.
5. Confirm `provider_event_id`, `provider_html_link`, and attendees are stored once per meeting.

### Meeting CRM Sync Failure

1. Inspect the `MeetingHandoff.crm_sync_status`, `crm_sync_error`, and affected `MeetingFollowUpTask` rows.
2. Confirm Attio credentials and meeting object/list mappings behind `CrmClient`.
3. Retry with `POST /v1/meetings/{meeting_id}/retry-sync` or the `ghostrecon.retry_meeting_crm_sync` task; do not recreate the meeting.
4. Preserve outcome notes and follow-up task IDs; retries must upsert by `ghostrecon_meeting:{meeting_id}`.
5. Surface unresolved failures in reporting until `crm_sync_status=succeeded`.

### Stale or Missing Meeting Prep Packet

1. Confirm the meeting exists and references the expected exported CRM target, account, contact, and optional sequence enrollment.
2. Regenerate with `POST /v1/meetings/{meeting_id}/prep-packet` using an idempotency key.
3. Check account/contact/signal freshness and any linked event or incident evidence before using the packet externally.
4. If canonical state changed materially after packet generation, create a new packet rather than editing the old source snapshot.

### Suppression or Governance Errors

1. Pause CRM export mutations and sequence enrollment for affected candidates.
2. Check `governance-service` logs, source-policy state, approval projections, and suppression tables.
3. Re-run policy and suppression reconciliation.
4. Audit any affected export or outbound action before replaying.

## Escalation Evidence

Every escalation should include correlation ID, service/source ID, canonical entity ID, fetch or outbox watermark, idempotency key, policy version, audit ID, timestamps in UTC, and the operator action already attempted. Do not attach unlicensed article bodies or prohibited personal data.
