# Sprint 25a Security Foundation

## Status

Sprint 25a provides shared security primitives and a database foundation. It is not an end-to-end
authentication or authorization implementation. Production integration remains tracked as Sprint
25b in [the sprint tracker](../SPRINTS.md), and the complete research requirements are preserved in
[SPRINT_25.md](../SPRINT_25.md).

The current gateway and console still use legacy actor and role parameters in local/test workflows.
Staging and production are strict profiles: the shared perimeter rejects caller-supplied identity
headers before any route runs. Because replacement OIDC/session and workload-authentication
middleware does not yet exist, the current operator flow is not production-ready.

## Implemented contracts

### Normalized identity and authorization

`IdentityContext` is an immutable business/data-access contract for human, service, and worker
identity. It carries the verified subject, issuer, audiences, roles, permissions, calling service,
represented subject, authentication method/time, assurance, session/correlation/request IDs,
mapping and policy versions, environment, workspace, and bounded attributes. Provider claims and
credentials are intentionally absent.

Human roles are additive:

| Role | Permission groups |
| --- | --- |
| `viewer` | session/profile self-service, canonical reads, reporting reads |
| `analyst` | viewer permissions plus intelligence, enrichment, scoring, watch, CRM export, sequencing, meeting, and assigned-work mutations |
| `governance_reviewer` | viewer permissions plus governance read/annotate/decide/override and suppression mutations |
| `administrator` | viewer, analyst, governance, security administration/audit, metrics, and documentation permissions |

Unknown roles grant no permissions. Authorization can require email-OTP, phishing-resistant, or
workload assurance and can require authentication no older than a configured bound. These checks
are library functions only; routes and repositories do not yet invoke them consistently.

### OIDC, service tokens, and sessions

The OIDC helpers implement HTTPS issuer anchoring, provider metadata validation, Authorization Code
parameters with PKCE S256/state/nonce, safe relative return paths, one-MiB provider JSON bounds,
RSA JWKS selection, an explicit RS256/RS384/RS512 allowlist, 2048-bit minimum RSA keys, and strict
ID-token issuer/audience/authorized-party/nonce/time validation.

The helpers do not fetch discovery/JWKS documents, exchange authorization codes, persist or consume
transactions, expose login/callback/logout routes, map claims, or rotate provider keys.

Internal helpers sign and verify Ed25519 JWTs with required key ID, token purpose, issuer, subject,
audience, time bounds, and `jti`. Service claims default to 120 seconds and allow at most 300
seconds. On-behalf-of claims last 45 seconds and bind the represented human to an audience,
operation, correlation ID, assurance, authentication method/time, and mapping/policy versions.
No process currently loads trust bundles, signs requests/tasks, verifies these tokens in middleware,
or persists replay markers.

Session helpers generate independent opaque identifiers and CSRF values, store only SHA-256 HMAC
digests, require at least a 256-bit HMAC key, and reserve `__Host-ghostrecon_session` and
`__Host-ghostrecon_oidc_transaction` cookie names. Session repositories, cookie issuance,
rotation, expiry, revocation, and CSRF enforcement remain unimplemented.

### Shared HTTP perimeter

Every FastAPI application built by `create_base_app` installs `SecurityPerimeterMiddleware`.

| Behavior | Current implementation |
| --- | --- |
| Correlation | Accepts `[A-Za-z0-9._-]{1,128}` or generates a value; returns `X-Correlation-ID` |
| Header bound | Rejects aggregate request headers above 16 KiB with 431 |
| Query bound | Rejects query strings above 8 KiB with 414 |
| Body bound | Rejects an invalid or greater-than-1-MiB declared `Content-Length` with 413; absent and streamed/chunked body accounting is not implemented |
| Legacy identity headers | Rejects `X-Actor`, `X-Operator-Role`, `X-User`, `X-User-Role`, and `X-User-Email` only in staging/production |
| Internal headers | Rejects external `X-GhostRecon-OBO` and `X-GhostRecon-Service-Authorization` in strict profiles; no trusted internal-request verifier is wired |
| Response headers | Adds correlation ID, no-sniff, no-referrer, restrictive permissions policy, and frame denial |
| Strict response headers | Adds HSTS and `Cache-Control: no-store` outside `/healthz` in staging/production |

Perimeter failures use `{code, message, correlation_id}`. Ordinary application errors retain their
existing shapes. Authentication, authorization, CORS, CSRF, trusted-proxy/TLS verification,
distributed rate limiting, route-specific bounds, CSP, and uniform errors remain Sprint 25b work.

### Operation policy registry

The initial registry classifies nine intended operations: login, callback, session read, logout,
security user administration, security audit read, health, readiness, metrics, and documentation.
Each policy declares owner, permission, authentication mode, assurance, RLS/audit/CSRF needs, rate
class, body limit, exposure, and allowed callers.

This registry is declarative. It is not bound to FastAPI routes or non-route operations, does not
enforce policy, and is not a complete permission matrix. In particular, `/readyz`, `/metrics`,
`/docs`, `/redoc`, and `/openapi.json` remain mounted without registry enforcement even though the
target policies describe restricted or disabled exposure.

## Database foundation

Migration `0015_security_foundation` creates:

- `security_principals` and expiring `security_role_bindings`;
- digest-only `security_sessions` with assurance, rotation, expiry, revocation, mapping, and policy state;
- bounded `security_emergency_grants`;
- expiring `security_replay_markers`;
- monotonic `security_policy_versions`; and
- additional verified identity, decision, assurance, version, request/correlation, bounded network metadata, and integrity-HMAC columns on `audit_events`.

`set_security_context` writes subject, identity type, calling/represented subjects, operation,
permissions, policy version, governance capability, and correlation ID through bound
`set_config(..., true)` calls. Values are transaction-local and clear before pooled connection
reuse. Repositories do not yet install this context automatically.

The migration creates SELECT policies for principal self/admin access, session self/admin access,
and security-audit readers. It does not execute `ENABLE ROW LEVEL SECURITY` or `FORCE ROW LEVEL
SECURITY`; therefore those policies are dormant. No application-table policies or runtime database
roles/grants exist. The current downgrade drops the three policies only and does not remove the new
tables, audit columns, or indexes. Treat `0015` as roll-forward-only until the downgrade is fixed.

## Current exposure and limitations

- No login, callback, session, refresh, step-up, logout, user-administration, or audit-query routes.
- No authoritative PostgreSQL/Redis session or OIDC transaction repositories.
- No authenticated gateway proxy, owner-service isolation, signed service calls/OBO propagation,
  worker identity, signed Celery tasks, replay enforcement, or key rotation.
- No complete route/operation matrix, database role model, application-table RLS, or forced RLS.
- No security-audit writer integration, redaction/aggregation policy, or fail-closed audit behavior.
- No CSRF, restrictive CORS, distributed limits, trusted-proxy/TLS enforcement, Dash CSP, or
  production system-endpoint authorization.
- No Helm OIDC/session/workload key configuration, NetworkPolicy rollout, deterministic local OIDC,
  Auth0 staging evidence, browser/service/database integration tests, or RLS performance evidence.

Do not describe the platform as production-authenticated, server-authorized, service-authenticated,
or RLS-enforced until the Sprint 25b acceptance evidence is complete.

## Verification

Run the focused foundation suite:

```bash
pytest -q tests/unit/test_security_foundation.py tests/unit/test_security_perimeter.py
```

See the [Sprint 25a evidence report](reports/sprint-25a-security-foundation.md) for the exact tested
surface and the test layers that remain outstanding.
