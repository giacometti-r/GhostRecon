# governance-service

## Purpose

`governance-service` owns source-reuse policy, incident corroboration decisions, suppression, lawful-basis metadata, retention, approval auditability, and replay controls. It is the fail-closed policy boundary for contact enrichment, CRM export, and every outbound action.

CRM export approval and outreach approval are separate decisions. Neither is implied by event/incident discovery.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=governance-service`

## Dependencies

- PostgreSQL source-policy, evidence, suppression, retention, approval, and audit tables.
- Event/incident intelligence services for source lineage and current canonical state.
- Console service for authenticated review workflows.
- CRM and sequencing services for enforcement at side-effect time.

## Operations

- Fail closed if reuse, corroboration, suppression, retention, lawful-basis, or approval state cannot be read.
- Require evidence and scope before setting participant reuse to `allowed`.
- Audit every approval, rejection, analyst corroboration, policy change, replay, suppression, and retention action.
- Invalidate eligibility when source policy, canonical identity, evidence, suppression, or material target data changes.
- Monitor blocked actions, policy-review expiry, approval age, suppression misses, replay count, and audit failures.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=governance-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
