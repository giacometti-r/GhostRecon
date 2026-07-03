# ADR 0001 - Python Microservices Instead Of n8n

## Status

Accepted.

## Context

The research recommended n8n as a modular orchestration layer. The implementation requirement changed to direct Python while preserving the same idea.

## Decision

Build explicit Python microservices with FastAPI and Celery. Keep the workflow stages separate by service boundary and share only stable libraries for schemas, observability, database access, and event contracts.

## Consequences

- More code ownership and testing responsibility than n8n.
- Better deployability, reviewability, source control, and Kubernetes fit.
- Easier to add strict governance, audit, replay, and typed contracts.
