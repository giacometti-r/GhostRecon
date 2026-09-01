# Sprint 25b production security evidence

Date: 2026-08-13

## Result

The deterministic Sprint 25b implementation gates pass. The runtime now has gateway-owned OIDC/session authentication, centralized route authorization, authenticated owner proxying, signed/replay-protected service and task envelopes, forced RLS migrations, gateway-only deployment topology, and hardened perimeter behavior. Sprint 25c tenant isolation remains required before E1 or real personal-data use.

Auth0 staging validation is `blocked_missing_environment_access`: no Auth0 test tenant credentials, email-OTP mailbox, or enrolled phishing-resistant authenticator were supplied. No live pass is claimed.

The image-scan/SBOM gate is `blocked_missing_tooling`: this host has neither Syft/Trivy nor the Docker SBOM plugin. The rebuilt image and all source gates passed, but release promotion must run the repository image scan and SBOM job in CI before publishing.

## Criterion-to-evidence

| Criterion | Evidence | State |
|---|---|---|
| Browser identity and sessions | OIDC discovery/JWKS/code client, encrypted one-time Redis transactions, opaque PostgreSQL sessions, CSRF, login/callback/refresh/step-up/logout APIs | passed deterministic |
| Security administration | AAL2/recent-auth user list/detail/atomic update, session list/revoke, audit query, 60-second bootstrap/emergency proofs | passed deterministic |
| Operation enforcement | Custom `SecurityRoute`; generated [operation JSON](../generated/operation-matrix.json) and [Markdown](../generated/operation-matrix.md); route coverage test | passed |
| Owner topology | Strict gateway owner proxy, gateway-to-console proxy, console workload/OBO calls, console owner handlers removed | passed |
| Workload/task trust | File Ed25519 keys, versioned trust bundles, audience/purpose validation, one-time OBO replay markers, signed JSON-only Celery base, ten queues plus scheduler | passed deterministic |
| RLS | Reversible 0015; staged 0016-0019 classification/roles/CRUD policies/enable/force; [RLS matrix](../generated/rls-matrix.md) | passed local Postgres |
| Missing/verified context | Non-owner insert without context denied; same insert with transaction-local verified context succeeded and rolled back | passed local Postgres |
| Deployment | Compose config; gateway-only app port; Helm local/external/production lint; TLS ingress, default deny, service accounts/key mounts, strict local-OIDC rejection | passed |
| Perimeter | identity-header denial, content/header/query/body bounds, JSON/compression/TLS/origin checks, Redis rate classes, HSTS/no-store/nosniff/frame/CSP | passed deterministic |
| Static/browser tests | Ruff, Bandit, full MyPy, full Pytest including Playwright | passed |
| Auth0 email OTP/passkey | External staging tenant unavailable | blocked_missing_environment_access |
| Image scan and SBOM | Scanner/plugin unavailable on workstation | blocked_missing_tooling |

## Commands and observed evidence

- `pytest -q`: 164 passed after Sprint tests were added.
- `mypy src`: 250 source files, no issues.
- `ruff check .`: passed.
- `bandit -q -r src`: passed; the local provider's OAuth `token_type=Bearer` protocol literal has a line-scoped B105 suppression.
- `sh scripts/check_helm.sh`: all three chart profiles linted, zero failures.
- `docker compose config --quiet`: passed.
- Fresh Compose migration image: upgraded through 0019, downgraded to 0014, and rolled forward through 0019.
- PostgreSQL catalog: 41 tables have both RLS enabled and forced; 29 GhostRecon roles are non-superuser/non-BYPASSRLS.
- `python scripts/generate_security_matrices.py --check`: passed.

## Rollout and rollback

Provision database login roles, Redis ACLs/namespaces, distinct private keys, trust bundles, and TLS/OIDC secrets before application rollout. Deploy owners accepting authenticated traffic, deploy the gateway/console mediation path, validate shadow comparisons, then enable/force RLS and remove legacy credentials. After forced RLS and credential revocation, roll forward only; never restore identity headers, runtime table ownership, bypass roles, unsigned tasks, or direct owner ingress.
