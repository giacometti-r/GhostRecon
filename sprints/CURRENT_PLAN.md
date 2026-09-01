# Sprint 25b — Production Identity, Workload Trust, RLS, and Perimeter

  ## Summary

  - Build on the Sprint 25a primitives and implement the complete Sprint 25b requirements from sprints/SPRINTS.md.
  - Current baseline: clean worktree; 157 tests, Ruff, Bandit, and Helm checks pass. MyPy has the single documented OIDC hash-algorithm error.
  - Current exposure: the gateway executes 90 domain routes in-process, including 51 mutations; identity remains caller-controlled; 16 Celery tasks lack signed delivery; 37 domain and 6
    security tables lack complete active RLS; Helm uses shared credentials and service accounts.

  - Preserve the existing /v1/... request/response contracts. Sprint 25c tenant isolation remains out of scope, so E1 stays blocked even after 25b completes.

  ## Identity, Authorization, and Gateway Changes

  ### OIDC and authoritative sessions

  - Add an async OIDC client with injectable HTTP transport, five-second timeouts, one-MiB streamed response limits, HTTPS-only strict issuers, bounded discovery/JWKS caches, unknown-kid
    refresh locks, rotation overlap, and fail-closed validation.

  - Use Auth0 Universal Login for email OTP and configured WebAuthn/passkey step-up. Email OTP maps to AAL1; only configured phishing-resistant acr/amr values map to AAL2. Follow Auth0’s
    current passwordless (https://auth0.com/docs/authenticate/passwordless) and step-up (https://auth0.com/docs/secure/multi-factor-authentication/step-up-authentication) contracts.

  - Store encrypted OIDC transactions in Redis for ten minutes. Atomically supersede and consume transactions, binding state, nonce, PKCE verifier, purpose, return path, and existing
    session reference to a separate host-only browser cookie.

  - Never persist codes, OTPs, provider tokens, or raw claims. Refresh provider role claims every five minutes through a prompt=none OIDC transaction; failed or stale refresh reduces the
    session to self-service permissions until interactive authentication succeeds.

  - Make PostgreSQL sessions authoritative and Redis a maximum-60-second cache. Store only HMAC digests, rotate identifiers every 15 minutes and after login/step-up/policy changes, and
    invalidate cache entries on every revocation.

  - Enforce the selected defaults: standard 8h idle/24h absolute; remembered 7d idle/30d absolute; privileged recent-authentication window 15 minutes. Strict profiles reject missing, zero,
    or unlimited values.

  - Use __Host-ghostrecon_session and __Host-ghostrecon_oidc_transaction, Secure in strict profiles, HttpOnly, SameSite=Lax, path /, and no domain attribute.

  ### Public API additions

  - Authentication routes:
      - GET /auth/login
      - GET /auth/callback
      - GET /auth/claims/refresh
      - GET /auth/step-up
      - GET /auth/provider-logout/callback
      - GET /auth/session
      - GET /auth/sessions
      - DELETE /auth/sessions/{session_id}
      - POST /auth/logout
      - POST /auth/logout-all
      - POST /auth/bootstrap-proof

  - Administrator routes, all requiring AAL2 and recent authentication:
      - GET /v1/security/users
      - GET /v1/security/users/{principal_id}
      - PATCH /v1/security/users/{principal_id} for activation, disablement, and atomic role changes with optimistic version and reason
      - GET /v1/security/users/{principal_id}/sessions
      - POST /v1/security/users/{principal_id}/sessions/revoke
      - POST /v1/security/emergency-grants/proof
      - GET /v1/security/audit

  - GET /auth/session returns assurance, expiry, roles, permissions, server-projected permitted actions, claim freshness, and the CSRF token; it never returns provider tokens or raw
    claims.

  - Standardize errors as {code, message, correlation_id}: 401 for missing/expired/stale authentication, 403 for permission/assurance/CSRF denial, existence-sensitive 404 after authorized
    lookup, 429 with Retry-After, and 503 for fail-closed security dependencies.

  ### Central operation enforcement

  - Expand OperationPolicy to cover method/path, owner, resource, human and service permissions, authentication mode, direct callers, OBO requirements, assurance and recent-authentication
    age, RLS, audit behavior, CSRF, rate class, body/bulk limits, exposure, expected denial semantics, and test IDs.

  - Keep human and service permissions as separate enums so administrators never inherit workload permissions.
  - Introduce immutable OperationContext containing verified identity, policy, resource scope, correlation metadata, and audit/database factories. Remove raw actor/role parameters and
    ReportingOperatorContext defaults from all business and persistence paths.

  - Bind every route to a custom APIRoute that resolves policy before parsing bodies or invoking handlers, following FastAPI’s supported custom route mechanism
    (https://fastapi.tiangolo.com/how-to/custom-request-and-route/).

  - Generate checked JSON and Markdown operation/RLS matrices. CI compares them with every FastAPI route, Dash action, Celery task, CLI operation, system endpoint, and ORM table and
    rejects missing or stale entries.

  ### Gateway and console topology

  - Make gateway routes use a proxying APIRoute: retain existing handler signatures for OpenAPI generation, but forward requests to the owning service instead of executing the shared
    handler.

  - Make the gateway reverse proxy / and Dash callback paths to internal console-service. Remove the eight owner handlers currently mounted in console.
  - Gateway authenticates the browser session before forwarding to console. Console uses its workload JWT plus an operation-bound represented-user envelope for API calls; gateway reloads
    authoritative session/provisioning state and signs a new owner-audience OBO envelope.

  - Owner services accept only direct service JWTs from allowed workloads and require OBO for human operations. Browser cookies, user bearer tokens, network location, and identity headers
    never authenticate an owner call.

  - Remove all X-Actor, X-Operator-Role, role selectors, role-name UI checks, static-token configuration/helpers, and default actor values. UI actions come only from /auth/session; add
    safe denied, expired-session, stale-claims, and step-up states.

  ## Workload, Database, and Perimeter Changes

  ### Workload trust and workers

  - Load Ed25519 private keys and versioned trust bundles from read-only files through credential-provider, signer/verifier, OBO, and replay-detector interfaces.
  - Use X-GhostRecon-Service-Authorization for direct workload JWTs and X-GhostRecon-OBO for represented users. Strip both namespaces at external ingress.
  - Use 120-second service JWTs and 45-second operation-bound OBO tokens. Replay-protect OBO and privileged service operations with atomic Redis SET NX EX, matching Redis’s documented
    atomic conditional-expiry behavior (https://redis.io/docs/latest/commands/set/).

  - Consolidate the duplicated worker modules into one task package and split deployments/queues:
      - source-fetch: generic/event/incident fetch
      - event-parser: event parsing
      - incident-parser: incident parsing
      - watch-monitor: watch monitoring
      - enrichment: crawl, resolution, contact enrichment
      - email-intelligence: candidate generation, persistence, verification
      - governance: suppression evaluation
      - crm-export: export batches
      - sequencing: due steps, inbound mail, alerts
      - meeting-sync: meeting CRM retry
      - scheduler: signed periodic publication only

  - Sign Celery headers over task name, canonical JSON argument digest, audience, queue, correlation/causation, expiry, and jti; validate in a common task base before run. Celery exposes
    mutable publish headers and worker request headers for this design in its signals (https://docs.celeryq.dev/en/latest/userguide/signals.html) and task request
    (https://docs.celeryq.dev/en/latest/userguide/tasks.html) contracts.

  - Accept JSON serialization only and reject unsigned, altered, replayed, expired, wrong-queue, wrong-audience, and unauthorized-producer tasks before database or provider access.

  ### Security persistence and RLS

  - Complete 0015_security_foundation downgrade for fresh/test environments, then add staged revisions:
      1. 0016_security_completion_schema: principal lifecycle/versioning, role revocation, session rotation/claim state, scope columns, indexes, and conservative backfill.
      2. 0017_security_roles_and_shadow_rls: least-privilege role groups, grants, separate CRUD policies, and shadow comparison tooling with RLS disabled.
      3. 0018_enable_grouped_rls: enable tested table groups.
      4. 0019_force_grouped_rls: force RLS after production-shaped evidence.

  - Classify all 37 domain tables and separately classify all 6 security tables. Force RLS on 35 domain tables plus all security tables; only cyber_events and organization_email_patterns
    remain explicit exclusions with narrow table grants and projected reads.

  - Add security_classification and scope_policy_version to protected domain rows. Add verified owner_subject to account/source/incident/watch/sequence/meeting roots, assignee_subject to
    human work queues, and owning_workload to worker-owned queue/output rows.

  - Backfill approved canonical data as internal, contact/provider/raw workflow data as restricted, governance/review/suppression data as governance, and every ambiguous legacy row as
    restricted with no verified owner or assignee.

  - Provision fixed NOLOGIN group roles for schema owner, migration, gateway security store, each owner runtime, reporting, session, audit writer/reader, retention, each worker queue, and
    tests. Deployment-specific LOGIN roles receive only one group and are validated as non-owner, non-superuser, and non-BYPASSRLS.

  - Install transaction-local verified context automatically in session_scope, using JSON permissions and explicit context-valid markers. Every policy also constrains the database role and
    calling workload.

  - Define separate SELECT/INSERT/UPDATE/DELETE policies with both USING and WITH CHECK; protect reclassification, reassignment, foreign-key scope, bulk writes, reports/exports, queues,
    and append-only audit.

  - PostgreSQL owners and BYPASSRLS roles otherwise bypass policies, so runtime role validation and final FORCE ROW LEVEL SECURITY are mandatory. See the PostgreSQL row-security rules
    (https://www.postgresql.org/docs/18/ddl-rowsecurity.html).

  ### Audit and bootstrap

  - Derive append-only audit events only from OperationContext; include verified human/service identities, OBO subject, permission, operation/resource, assurance, policy versions,
    environment, request/correlation IDs, bounded network metadata, decision, and per-entry HMAC.

  - Commit privileged mutation audit in the same transaction as the mutation. If it cannot persist, roll back and return 503. Audit privileged denials separately; aggregate only pre-
    authorization rate-limit noise in Redis to avoid denial-log amplification.

  - Add deterministic recursive redaction for credentials, cookies, tokens, email content, provider payloads, and exception details.
  - First-admin bootstrap requires an AAL2 session to create a one-time 60-second bootstrap proof. The CLI consumes it under the migration credential, succeeds only when no administrator
    exists, and requires reason and approver evidence.

  - Emergency grants use the same proof pattern, require a separate target and approver, expire within one hour, cannot grant service/database bypass, and remain subject to ordinary RBAC,
    service authentication, and RLS.

  ### Perimeter and deployment

  - Enforce middleware order: correlation/trusted proxy → reserved-header and structural bounds → operation resolution → anonymous rate limit → authentication → identity rate limit → CSRF
    → authorization/assurance → audit context → handler/proxy.

  - Require JSON and exactly one valid Content-Length for strict unsafe APIs; reject conflicting/malformed lengths and non-identity content encoding. Independently count ASGI body chunks
    and abort on underrun, overrun, or operation-specific limit before parsing.

  - Retain 16-KiB total headers and 8-KiB query defaults; add cookie count/size, query item/value, per-header, and bulk-item limits.
  - Initial distributed rate defaults, environment-configurable: auth 5/min and 20/hour per IP/browser, callbacks 20/min, sessions 60/min, reads 300/min, expensive reads 60/min, mutations
    60/min, bulk/export 10/min, owner calls 600/min per caller/operation. Auth, privileged, mutation, bulk, and owner classes fail closed when Redis is unavailable; ordinary reads use a
    small local fallback and emit degraded security evidence.

  - Require X-CSRF-Token on every browser unsafe request. Dash fetches it from /auth/session, keeps it only in memory, and attaches it only to same-origin requests.
  - Apply exact-origin CORS, trusted ingress CIDRs, TLS-derived secure request validation, HSTS, no-store, nosniff, frame denial, and Dash CSP hashes/nonces without unsafe-eval.
  - Leave only /healthz anonymous. Require service authentication for readiness and metrics; disable docs/OpenAPI/Redoc in strict profiles unless explicitly enabled for an AAL2
    administrator.

  - Helm/Compose changes:
      - Gateway-only external port and TLS ingress; console and owners remain ClusterIP/internal.
      - Default-deny application NetworkPolicies with explicit gateway, console, owner, worker, Redis, PostgreSQL, DNS, probe, and metrics flows.
      - Distinct service accounts with token automount disabled.
      - Distinct database DSNs, Redis ACL users/namespaces, private-key mounts, and trust bundles per workload.
      - Remove provider credentials from gateway and all unrelated workloads.
      - Add a separate deterministic local OIDC service only to local/test Compose and guarded local chart values; strict rendering or startup must reject it.

  ## Verification and Evidence

  - Unit tests: OIDC exchange/claims/JWKS rotation, transaction encryption/replay, session lifecycle, role intersection, assurance, CSRF, rate limits, body streaming, redaction, audit
    failure, key loading/rotation, OBO, task signatures, and configuration rejection.

  - Contract tests: every gateway/owner/auth/system route has explicit policy and security scheme; all 90 existing gateway contracts remain shape-compatible; unclassified routes, tasks,
    Dash actions, CLI operations, or tables fail CI.

  - PostgreSQL/Redis integration: real non-owner roles; missing-context denial; allowed/denied CRUD and transitions; shadow versus RLS comparison; forced policies; rollback/exception/
    cancellation/pool cleanup; audit append-only behavior; Redis replay, revocation, atomic transaction consumption, multi-replica limits, and unavailable-Redis behavior.

  - Service/worker tests: direct browser and anonymous owner calls, wrong key/issuer/subject/audience/purpose/caller, OBO modification/replay, key overlap/removal, unsigned/altered/
    replayed tasks, wrong queue/producer, and secret-free logs.

  - Browser tests with deterministic local OIDC: login, OTP-style callback, open-redirect and replay rejection, session rotation/expiry, CSRF, logout scopes, stale claims, denied actions,
    AAL2 step-up, no role selector, gateway-only console navigation, and CSP.

  - Helm tests: gateway-only TLS ingress, no strict local OIDC, distinct accounts/credentials/keys, NetworkPolicies, Redis ACLs, secure cookie/config validation, and negative renders for
    wildcard CORS, public docs/metrics, insecure issuer, missing keys, shared DB credentials, owner ingress, or mutable identity paths.

  - Mandatory gates: Ruff, Bandit, full MyPy—including the existing concrete OIDC hash typing fix—full tests, migration upgrade/downgrade/roll-forward, operation/RLS matrix checks, browser
    tests, Helm negative rendering, image scan, and SBOM.

  - Add a redacted Auth0 staging harness for email OTP and phishing-resistant step-up. Per the selected assumption, record it as blocked_missing_environment_access unless credentials are
    supplied; never fabricate a pass.

  - Publish the production-security ADR, generated operation/RLS matrices, authentication/service/task/key-rotation/database guides, Helm/secrets and local/staging guides, incident/
    bootstrap/recovery runbooks, affected service documentation, and docs/reports/sprint-25b-production-security.md.

  - Run final consistency searches for legacy headers, actor/role parameters, demo selectors, static tokens, public system endpoints, unclassified operations/tables, shared credentials,
    and direct owner access; finish with graphify update ..

  ## Rollout, Rollback, and Completion

  - Roll out in waves: provision roles/keys/Redis ACLs → deploy compatible owner authentication and gateway proxying → run shadow RLS → enable and force tested groups → canary Auth0 users
    → expose only gateway → revoke legacy credentials and remove compatibility behavior.

  - Roll back application images only to Sprint-25-compatible versions or roll forward. Production rollback must never restore caller-asserted identity, public owner access, allow-all
    policies, table-owner runtime credentials, or disabled RLS.

  - Migration downgrades remain testable for fresh/pre-production recovery, but the production runbook forbids downgrading past forced-RLS revisions after runtime credentials are revoked.
  - Sprint 25b is complete when deterministic, integration, browser, deployment, documentation, and matrix evidence pass; Auth0 evidence is honestly recorded as blocked if access remains
    unavailable. E1 remains explicitly blocked until Sprint 25c adds end-to-end tenant context and isolation.