# ADR 0007: Production identity, workload trust, and forced RLS

Status: accepted, 2026-08-13.

## Decision

Use generic OIDC authorization-code flow with PKCE and nonce at the gateway, with Auth0 Universal Login as the reference production provider. Email OTP is AAL1; only configured phishing-resistant `amr` values satisfy AAL2. Store only opaque, HMAC-digested, revocable server sessions.

Use the gateway as sole ingress and policy enforcement point. Preserve owner-service independence by forwarding with distinct Ed25519 workload JWTs and short-lived, audience- and operation-bound OBO envelopes. Replay-protect OBO and signed JSON-only Celery tasks in Redis. Use distinct workload service accounts and filesystem-mounted credentials; SPIFFE remains a future migration option.

Use additive human RBAC and keep workload authorization separate. Derive audit/database context from verified identity, never caller headers. Stage conservative table classification, shadow CRUD policies, enabled RLS, then forced RLS under non-owner/non-bypass roles. Local/test may use the deterministic local OIDC harness; strict profiles reject it.

## Consequences

Security dependencies fail closed for authentication and mutations. Provider outage does not turn into a bypass. Key rotation requires public-key overlap. Production migration rollback cannot restore untrusted identity, owner credentials, or disabled RLS. Sprint 25c is still required before shared-SaaS tenant isolation or E1 approval.

## Rejected alternatives

Static bearer secrets, identity headers, browser calls to owners, symmetric shared workload keys, unsigned task payloads, database-owner runtime connections, security-definer bypass, role selection in the UI, and allow-all RLS policies are rejected.
