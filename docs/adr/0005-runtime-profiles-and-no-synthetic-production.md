# ADR 0005: Runtime Profiles, Credential Ownership, and No-Synthetic Production

- Status: Accepted
- Date: 2026-07-20

## Context

GhostRecon previously used an environment selector with ambiguous values, defaulted several
providers to local demo adapters, inferred CRM and calendar fakes from missing credentials, and
exposed every Helm secret to every workload. Those behaviors made an incomplete deployment look
healthy and allowed synthetic lineage to escape the demo boundary.

## Decision

GHOSTRECON_PROFILE is the only runtime selector. Its values are local, test, staging, and
production; the retired selector and unknown values are errors. Every process has a published
dependency descriptor and validates only its owned settings before application, Celery, migration,
or seed construction. Validation failures are structured and redact values.

Local demo adapters and deterministic domain inference are limited to local. Tests may inject
fakes explicitly. Staging and production require live providers, identifying crawler/geocoder user
agents, safe endpoints, non-placeholder credentials, and valid Google RSA key material. A session
flush guard rejects exact synthetic provider/lineage sentinels in strict profiles.

Helm projects secret keys per workload, runs service-scoped preflight hooks, and requires SHA-256
image digests for every deployed image in strict profiles. CI produces migration, browser, Helm,
vulnerability-scan, and SPDX/CycloneDX evidence. Live-provider checks run only through the protected
staging environment and use bounded read-only or protocol no-op operations.

## Consequences

A strict deployment fails before traffic when configuration is incomplete. Adding a provider or
task now requires updating the dependency registry, its Helm secret projection, preflight tests, and
operations documentation. Compose remains an explicitly local deterministic demo.
