# Production security operations

Sprint 25b makes `gateway-service` the only browser/API ingress. Strict profiles use generic OIDC (Auth0 is the reference configuration), opaque PostgreSQL-authoritative sessions, session-bound CSRF, and centrally classified operations. Owner services accept only audience-bound Ed25519 workload JWTs; represented human calls additionally require a one-time, operation-bound OBO token.

## Credentials and rotation

Each service, queue worker, scheduler, probe, and metrics collector needs a distinct environment-scoped Ed25519 identity. Mount its private key read-only and publish only public keys in the trust bundle. Add the replacement public key, deploy replacement signers, wait longer than the maximum five-minute service-token lifetime, then remove the old key. Never place migration credentials in runtime trust bundles.

Session, OIDC-transaction, and audit HMAC/encryption keys are secret values. Changing session or policy versions invalidates affected sessions. Provider authorization codes, OTPs, access tokens, and raw claims are not persisted.

## Database and RLS

Migrations 0016 through 0019 add conservative classifications and scope fields, create fixed `NOLOGIN`, `NOSUPERUSER`, `NOBYPASSRLS` roles and separate CRUD policies, then enable and force RLS. Runtime login roles must inherit exactly one group role and must not own protected tables. Repository transactions install verified context with transaction-local `set_config`; missing context denies writes. Production rollback is roll-forward only after runtime credentials have been revoked.

## Bootstrap and emergency recovery

An existing phishing-resistant administrator with authentication no older than 15 minutes requests `/auth/bootstrap-proof` or `/v1/security/emergency-grants/proof`. Proofs are random, stored only as SHA-256 digests in Redis, expire after 60 seconds, and are one-time inputs for privileged CLI workflows. Record reason and separate approver evidence. Emergency grants may last at most one hour and never grant service, database-owner, superuser, or RLS-bypass capability.

## Failure behavior

OIDC/JWKS, Redis replay, strict mutation rate limits, session persistence, workload verification, and privileged audit are fail closed. `/healthz` is the only generally anonymous system endpoint; readiness and metrics require their named workload identities. Strict profiles disable OpenAPI/Swagger/Redoc. Security errors use `code`, `message`, and `correlation_id` and omit exception/provider detail.

Generated inventories: [operation matrix](generated/operation-matrix.md) and [RLS matrix](generated/rls-matrix.md).
