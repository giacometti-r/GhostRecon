# Sprint 25a Security Foundation Evidence

## Result

Sprint 25a delivers a unit-tested foundation, not the Sprint 25 production outcome. On 2026-07-30,
the focused command below completed with 14 passing tests:

```bash
pytest -q tests/unit/test_security_foundation.py tests/unit/test_security_perimeter.py
```

## Implemented evidence

| Capability | Implementation | Evidence |
| --- | --- | --- |
| Immutable normalized identity | `security/identity.py` | Identity copies mutable attributes and validates required/time-aware fields |
| Additive RBAC and assurance | `security/policy.py` | Unknown-role denial, governance/analyst separation, step-up and recent-authentication tests |
| Workload and OBO JWT primitives | `security/jwt.py` | Audience, purpose, lifetime, signature, and 45-second OBO binding tests |
| OIDC validation primitives | `security/oidc.py` | PKCE/open-redirect, HTTPS metadata, RSA ID-token validation, and negative-claim tests |
| Opaque session/CSRF secrets | `security/sessions.py` | HMAC key length, digest-only storage, and verification tests |
| Initial operation policy | `security/operations.py` | Explicit system/security policy and duplicate/unclassified-operation behavior |
| Shared transport perimeter | `security/perimeter.py`, `common/service.py` | Strict legacy/internal-header rejection, declared body bound, correlation, and security-header tests |
| Security persistence | `models/db/security.py`, `models/db/governance.py` | ORM registration and migration `0015_security_foundation`; no database integration test in this slice |
| Transaction database context | `security/database.py` | Bound transaction-local settings; no PostgreSQL integration test in this slice |

## Explicitly absent evidence

- No browser, API authentication, login/callback, session repository, CSRF, or denied-UX tests.
- No route/operation completeness or authorization-enforcement matrix.
- No owner-service, gateway proxy, workload trust, OBO propagation, replay, key-rotation, or signed-task tests.
- No PostgreSQL migration execution, downgrade, database-role, enabled/forced RLS, connection-pool,
  CRUD-policy, reporting/export, worker-isolation, query-plan, or latency tests for this slice.
- No Redis transaction/session/rate-limit/replay integration tests.
- No security-audit persistence, redaction, flood-control, or fail-closed audit tests.
- No Helm/NetworkPolicy/key-projection, deterministic local OIDC, Auth0 staging, or live-provider
  evidence.

These gaps are Sprint 25b work. They must not be marked passed or inapplicable without new evidence.

## Documentation evidence

- [Sprint tracker](../../SPRINTS.md) separates the completed foundation from Sprint 25b.
- [Security foundation reference](../security-foundation.md) publishes exact current behavior and
  limitations.
- [ADR 0006](../adr/0006-security-foundation.md) records the provisional architecture and staged
  enforcement decision.
- [Sprint 25 research](../../SPRINT_25.md) preserves the complete target acceptance criteria.

## Completion rule

This report is foundation evidence only. A separate Sprint 25b completion report must map every
production acceptance criterion to implementation, tests, deployment/staging evidence, and final
documentation consistency results.
