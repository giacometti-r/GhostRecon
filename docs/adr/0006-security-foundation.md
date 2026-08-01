# ADR 0006: Security Foundation and Staged Production Enforcement

- Status: Provisional
- Date: 2026-07-30

## Context

GhostRecon currently has demo-oriented actor and role propagation, independently exposed service
routes, public system endpoints, and one shared application database role. Sprint 25 requires OIDC
users, authoritative revocable sessions, centralized RBAC and assurance, authenticated workloads,
on-behalf-of propagation, protected system endpoints, security auditing, least-privilege database
roles, and risk-based RLS.

Delivering all enforcement layers atomically would couple identity-provider, browser, gateway,
service, worker, database, Redis, Helm, and operational changes. A partially wired security flow can
also create false assurance. The first delivery is therefore an explicitly non-production
foundation with its remaining gaps documented.

## Decision

- Normalize verified human, service, and worker identity into one immutable `IdentityContext` that
  excludes raw provider claims and credentials.
- Use additive server-side permissions for viewer, analyst, governance reviewer, and administrator;
  unknown roles grant nothing. Separate email-OTP, phishing-resistant, and workload assurance and
  allow recent-authentication requirements for sensitive operations.
- Remain a generic OIDC relying party. Use Authorization Code with PKCE S256, state, nonce, HTTPS
  issuer anchoring, explicit asymmetric algorithms, bounded metadata/JWKS, and opaque server-side
  sessions. Auth0 is a staging reference provider, not a provider-specific application boundary.
- Treat email OTP as baseline assurance, not phishing-resistant step-up.
- Use short-lived Ed25519 JWTs for workload identity and distinct operation-bound OBO envelopes for
  represented users. Calling workload and represented human remain separate identities.
- Make the gateway the future sole ingress and policy decision point; owner services will accept
  only authenticated, allowed workloads and will independently validate OBO context.
- Define operation policy in code and generate route/non-route matrices from it. Until route binding
  and completeness checks exist, the initial registry is descriptive only.
- Store only HMAC digests for opaque session and CSRF secrets. PostgreSQL is authoritative for
  revocation; Redis will hold bounded transactions, cache, rate-limit, and replay state.
- Pass verified identity into PostgreSQL using transaction-local bound `set_config` calls. Introduce
  least-privilege runtime roles and RLS in stages: schema/scope, policies, shadow validation,
  `ENABLE ROW LEVEL SECURITY`, then `FORCE ROW LEVEL SECURITY` only after production-shaped tests.
- Expand audit records for verified human/service/OBO identity, permission decision, assurance,
  policy versions, environment, correlation/request IDs, bounded network metadata, and integrity.
- Keep local deterministic identity infrastructure impossible to enable in staging/production.
- Prefer roll-forward or Sprint-25-compatible rollback; never restore caller-asserted production
  identity, bypass RLS/audit, or grant runtime superuser/`BYPASSRLS` access.

## Foundation boundary

Sprint 25a implements only the shared types, cryptographic/validation helpers, session-secret
helpers, initial operation registry, HTTP transport perimeter, security schema, audit columns,
transaction-context helper, dormant SELECT policies, and focused unit tests.

It does not implement OIDC routes/repositories, session lifecycle, authorization middleware,
workload credential loading, signed requests/tasks, replay enforcement, gateway mediation,
database roles, enabled/forced RLS, security-audit persistence, deployment changes, or production
acceptance evidence. See [the security foundation reference](../security-foundation.md).

## Consequences

- The foundation can be tested independently and reused by gateway, owner services, workers, and
  repositories without locking the application to Auth0.
- Strict profiles reject legacy identity headers before replacement authentication exists. This is
  a deliberate fail-closed boundary but means the current console workflow is not production-ready.
- The operation registry may not be treated as effective authorization, and the created RLS
  policies may not be treated as enforced until their activation stages are complete.
- Migration `0015_security_foundation` is currently roll-forward-only because its downgrade removes
  policies but not the added schema.
- Security documentation must label every behavior as implemented foundation, known limitation, or
  Sprint 25b target.

## Rejected alternatives

- Caller-supplied actor/role headers or a production demo-role selector.
- Application-managed passwordless credentials instead of a trusted OIDC provider.
- Browser storage of provider tokens or long-lived bearer service secrets.
- Symmetric shared service keys across workloads or trusting OBO without direct service identity.
- Authorization based only on UI hiding, route-name conventions, or role-name comparisons.
- Immediate untested `FORCE ROW LEVEL SECURITY`, allow-all transition policies, security-definer
  bypasses, runtime table ownership, superuser rollback, or `BYPASSRLS`.
- Public production metrics/docs by default or a single shared ingress/database credential model.

## Future direction

Sprint 25b completes the gateway, session, workload, audit, database, deployment, and evidence
layers. A later migration to SPIFFE/SPIRE may replace file-mounted workload credentials while
preserving the signer/verifier and normalized identity contracts.
