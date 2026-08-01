# Sprint 25 Research - Passwordless OIDC Identity, Server-Side RBAC, Service Authentication, Row-Level Security, and Secured API Perimeter

This document preserves the authoritative research and acceptance criteria that informed the
Sprint 25 security work. It describes the complete target state, not the current implementation.
The implemented foundation and remaining production work are tracked in [SPRINTS.md](SPRINTS.md).

Objective and production outcome

Replace all caller-asserted demo identity with cryptographically verified user identity, cryptographically verified service identity, one authoritative server-side permission model, and database-enforced row-level security for security-sensitive records.

The resulting production system must provide:

1. Passwordless user authentication through a trusted OpenID Connect identity provider using email-delivered one-time codes.
2. OIDC Authorization Code flow with PKCE, state, and nonce.
3. Secure, bounded, rotated, revocable browser sessions using opaque cookies.
4. Strict JWT validation for all authenticated API calls.
5. Signed and independently authenticated service-to-service identity.
6. One centralized server-side permission model for all human roles and named service identities.
7. Database row-level security for restricted, assigned, owned, governance-sensitive, and service-specific records.
8. Explicit protection for console, gateway, owner services, callbacks, reporting, mutations, bulk operations, source operations, governance data, metrics, documentation, health endpoints, system endpoints, workers, event consumers, exports, and administrative paths.
9. Consistent 401 and 403 behavior.
10. Safe, redacted, traceable auditing of allowed and denied privileged operations.
11. Secure-by-default deployment and Helm configuration.
12. Complete deterministic test coverage across unit, integration, database, API contract, browser, deployment, staging, and live-provider validation layers.
13. Complete documentation, ADRs, configuration references, operational procedures, and final consistency checks.

Current implementation and known risks

The current implementation contains demo-oriented identity handling and inconsistent authorization behavior.

Known conditions include:

1. src/ghostrecon/common/security.py performs static token comparison but does not provide application-wide authentication and authorization middleware.
2. Routers under src/ghostrecon/service_apps/routers/ accept caller-controlled identity and role headers such as X-Actor and X-Operator-Role.
3. src/ghostrecon/console/ exposes and forwards demo role selections.
4. Authorization behavior differs across callbacks, reporting, mutations, bulk operations, source actions, metrics, documentation, system endpoints, gateway routes, and owner-service APIs.
5. Internal services do not yet use one mandatory service-authentication model.
6. Database access is not explicitly constrained by row-level security.
7. A caller may be able to influence audit identity or authorization by supplying identity-related headers.
8. Session lifecycle, revocation, logout scope, role-change handling, and privileged reauthentication are not yet consistently specified.
9. Local role selection may remain only as an explicitly local or test-only authentication backend that is technically impossible to enable in staging or production.
10. Sprint 25 depends on Sprint 24 validation for issuer configuration, client configuration, redirect URIs, session secrets, service credentials, environment controls, and deployment secret handling.

Non-goals

The following are excluded from Sprint 25:

1. Multi-workspace or multi-tenant authorization.
2. Cross-workspace access models.
3. Tenant administration.
4. User-managed passwords.
5. Application-generated password-reset flows.
6. Social login unless already provided by the selected OIDC provider.
7. Anonymous privileged access.
8. Client-side authorization as a security boundary.
9. Replacing all business logic with database policies.
10. Using database row-level security as a substitute for API authorization.
11. Long-lived bearer credentials for services.
12. Permanent browser sessions that remain valid indefinitely until cookies are deleted.

Security principles

The implementation must follow these principles:

1. Never trust identity, actor, role, email, subject, service name, permission, or forwarding headers supplied by an external caller.
2. Derive user identity only from verified OIDC authentication results or verified JWT claims.
3. Derive service identity only from cryptographically verified service credentials.
4. Enforce authorization only on the server.
5. Default deny when authentication, claim mapping, role mapping, permission mapping, database identity context, service identity, or policy evaluation is missing or unknown.
6. Treat CORS as a browser control, not as an authentication or authorization mechanism.
7. Require both application-level authorization and database-level row restrictions where row-level security applies.
8. Do not log access tokens, ID tokens, refresh tokens, authorization codes, one-time email codes, session cookies, CSRF tokens, private keys, client secrets, raw authentication responses, or unnecessary claims.
9. Use least privilege for users, services, workers, database roles, and deployment credentials.
10. Fail closed when trusted identity metadata, signing keys, session validation, permission configuration, or row-level security context cannot be established.
11. Keep ordinary CI deterministic and independent of external identity-provider availability.
12. Make all production security behavior explicit and testable.

Passwordless login requirements

The application must support passwordless login using an email-delivered one-time code.

The preferred architecture is that the trusted OIDC identity provider performs the email-code challenge and verification. The application remains an OIDC relying party and must not create a separate application-specific passwordless identity system unless the application is explicitly designated as the credential provider.

Required user flow:

1. The user opens the login page.
2. The user enters an email address or initiates login through a provider-hosted login page.
3. The browser is redirected to the trusted OIDC provider.
4. The provider creates a transaction-specific authentication challenge.
5. The provider sends a six-digit one-time code to the user’s verified email address.
6. The user enters the code at the provider.
7. The provider validates the code.
8. The provider completes OIDC authentication.
9. The provider redirects the browser to the application callback with an authorization code.
10. The application validates state, nonce, redirect URI, issuer, token response, PKCE verifier, claims, and signature.
11. The application creates an opaque server-side browser session.
12. The application sends only a secure session cookie to the browser.
13. The application redirects the user to the authenticated console.
14. The application must not expose provider tokens to browser JavaScript.
15. The application must not store raw tokens in localStorage, sessionStorage, IndexedDB, browser-visible cookies, URLs, analytics, or logs.

Email-code security requirements

If the identity provider exposes configuration for the email-code method, require:

1. Exactly six numeric digits unless the provider requires a different format.
2. Cryptographically secure random generation.
3. Single-use behavior.
4. A short lifetime, normally no more than ten minutes.
5. A maximum number of verification attempts per challenge.
6. Challenge invalidation after successful verification.
7. Challenge invalidation when a replacement code is issued.
8. Binding to a single authentication transaction.
9. Binding to the intended account or email address.
10. Binding to the expected OIDC client.
11. Protection against account enumeration.
12. Generic responses for unknown and known accounts where possible.
13. Rate limiting by account, email address, IP address, browser session, and device-risk signal where available.
14. Email-send throttling to prevent mailbox flooding.
15. Detection of excessive failed attempts.
16. Detection of suspicious login velocity.
17. No one-time code in application logs, audit events, query strings, URLs, traces, analytics, exception reports, or support diagnostics.
18. No plaintext persistence of one-time codes by the application.
19. No acceptance of a code outside the specific authentication transaction for which it was issued.
20. No reuse after successful authentication.
21. No fallback to a weak password flow unless explicitly approved and documented.
22. Clear handling of delayed, duplicate, and superseded email messages.
23. Clear expiration and retry UX.
24. No disclosure of whether an email address is registered when that disclosure is not required.

Authentication assurance policy

Email-code authentication must not automatically be treated as sufficient for every privileged operation.

Define authentication assurance requirements by role and operation.

At minimum:

1. Viewer accounts may use email-code authentication.
2. Analyst accounts may use email-code authentication, subject to risk controls.
3. Governance reviewers must use step-up authentication for designated sensitive operations.
4. Administrators must use a stronger authentication method, preferably passkey or WebAuthn, or a provider-supported phishing-resistant factor.
5. Service identities must never authenticate through email.
6. High-risk operations must require recent authentication.
7. The system must record the authentication method and authentication time in the normalized identity context when available.
8. The permission layer must be able to require a minimum authentication assurance level or recent-authentication age for selected permissions.

Operations that should be considered for step-up authentication include:

1. Administrator role or permission changes.
2. Governance approvals or overrides.
3. Bulk deletion.
4. Bulk mutation.
5. Credential creation, rotation, or revocation.
6. Integration configuration changes.
7. Service-identity changes.
8. Export of sensitive or governance-restricted data.
9. Session termination for other users.
10. Security-policy changes.
11. Audit-retention changes.
12. Emergency-access operations.
13. Destructive source actions.
14. Changes to issuer, client, audience, JWKS, session, or service-auth configuration.

OIDC protocol requirements

Implement OIDC Authorization Code flow with the following mandatory controls:

1. Authorization Code flow only for browser login.
2. PKCE using S256.
3. A cryptographically random state value for every login transaction.
4. A cryptographically random nonce for every login transaction.
5. Exact redirect URI matching.
6. No wildcard redirect URIs in production.
7. No authorization response handling on untrusted origins.
8. Short-lived login transaction state.
9. One-time use of state, nonce, and PKCE verifier.
10. Detection and rejection of replayed callbacks.
11. Validation that the callback belongs to the same browser login transaction.
12. Validation of issuer.
13. Validation of audience.
14. Validation of authorized party where applicable.
15. Validation of subject.
16. Validation of expiry.
17. Validation of not-before.
18. Validation of issued-at within an acceptable clock-skew policy.
19. Validation of nonce.
20. Validation of required claims.
21. Validation of token signature.
22. Validation against an explicit algorithm allowlist.
23. Rejection of unsigned tokens.
24. Rejection of none algorithm.
25. Rejection of algorithms not explicitly configured.
26. No algorithm selection based only on the untrusted token header.
27. No asymmetric-to-symmetric algorithm confusion.
28. No acceptance of provider metadata or JWKS locations supplied by an untrusted token.
29. Provider discovery only from explicitly configured trusted issuers.
30. HTTPS-only issuer metadata and JWKS retrieval in staging and production.
31. Controlled metadata and JWKS timeout behavior.
32. Controlled metadata and JWKS response-size limits.
33. Controlled JWKS caching.
34. Safe JWKS refresh on unknown key ID.
35. Rate-limited JWKS refresh to avoid denial-of-service behavior.
36. Support for provider signing-key rotation.
37. Fail-closed behavior when required signing keys cannot be obtained.
38. Exact issuer comparison.
39. Explicit audience configuration per API.
40. Separate audiences where appropriate for console, gateway, owner services, and internal APIs.
41. No acceptance of tokens issued for another client or API.
42. No token contents in error responses.
43. No provider authorization codes in logs.
44. No provider tokens in browser-visible storage.
45. No persistent storage of raw ID tokens or access tokens unless explicitly justified.
46. If refresh tokens are required, store them only server-side, encrypted, access-controlled, rotated, and revocable.
47. Prefer no refresh-token persistence when a server-side session can satisfy the product requirement.

Browser session requirements

After successful OIDC authentication, create a bounded server-side session.

Session design:

1. The browser cookie contains only a high-entropy opaque session identifier.
2. The authoritative session record is stored server-side.
3. The cookie must be Secure in staging and production.
4. The cookie must be HttpOnly.
5. The cookie must use an appropriate SameSite policy.
6. The cookie Path must be restricted appropriately.
7. The cookie Domain must not be broader than required.
8. The cookie name must use a secure production-safe convention.
9. The session identifier must be unguessable.
10. Session identifiers must be rotated after authentication.
11. Session identifiers must be rotated after privilege changes.
12. Session identifiers must be rotated after step-up authentication.
13. Session identifiers must be rotated periodically during long-lived sessions.
14. Old session identifiers must be invalidated after rotation.
15. Sessions must have an idle timeout.
16. Sessions must have an absolute maximum lifetime.
17. Remembered sessions must still have idle and absolute expiration.
18. No session may remain valid indefinitely only because a cookie remains in the browser.
19. Logout must invalidate the server-side session.
20. Account disablement must invalidate all active sessions.
21. Role removal must invalidate or refresh affected sessions.
22. Security-policy changes must be able to invalidate affected sessions.
23. Suspected session compromise must support revocation.
24. Administrators must be able to revoke all sessions for a user.
25. Users should be able to revoke their other sessions where product scope allows.
26. Session records must contain only necessary security state.
27. Session records must not contain raw access tokens, ID tokens, authorization codes, one-time codes, or unnecessary claims.
28. Session lookup must be resistant to timing and enumeration issues.
29. Expired sessions must be removed or rendered unusable.
30. Session cleanup must be bounded and operationally monitored.
31. Session storage must have retention and capacity controls.
32. Session cookies must not be readable by application JavaScript.
33. Session cookies must never be placed in URLs.
34. Session identifiers must never be logged.
35. Session expiry must result in a clear browser UX and consistent 401 handling.
36. Sensitive actions must be able to require recent authentication even when the session is otherwise valid.

Recommended initial session policy, subject to product approval:

1. Standard session idle timeout: 8 hours.
2. Standard session absolute lifetime: 24 hours.
3. Remembered session idle timeout: 7 days.
4. Remembered session absolute lifetime: 30 days.
5. Privileged-operation recent-authentication window: configurable, initially 15 minutes.
6. Session-policy values must be configurable by environment.
7. Production must enforce explicit finite values.
8. Zero, unlimited, or missing values must fail deployment validation.

Login, callback, logout, and session routes

Publish and document:

1. Login initiation route.
2. OIDC callback route.
3. Logout route.
4. Optional provider logout callback route.
5. Session status route.
6. Session-expired handling route or response behavior.
7. Reauthentication or step-up initiation route.
8. Reauthentication callback behavior.
9. Logout-all-sessions route if included.
10. Administrative session-revocation operation if included.

Required behavior:

1. Login initiation must create state, nonce, PKCE verifier, and transaction state.
2. Callback must validate the exact transaction.
3. Invalid, expired, missing, reused, or mismatched callback state must fail.
4. Callback failures must not reveal sensitive values.
5. Login CSRF must be prevented.
6. Logout must invalidate the server-side session.
7. Logout must not be a state-changing unauthenticated GET request.
8. Provider logout behavior must be explicitly defined.
9. Local logout, provider logout, and logout-all-devices must be distinguished.
10. Session-expired responses must not be confused with permission denial.
11. The console must show a safe denied or expired-session experience.
12. Open redirect behavior must be prevented.
13. Post-login return URLs must be validated against an allowlist or safe relative-path policy.

Normalized identity context

Create one normalized internal identity context used by middleware, authorization, auditing, services, workers, and database context setup.

The normalized context must distinguish human users from service identities.

Required fields should include only what is necessary, such as:

1. identity_type: human or service.
2. subject: stable verified subject identifier.
3. actor: normalized display identity where needed.
4. email: verified email only when required.
5. email_verified: provider-derived verification state where available.
6. issuer: trusted verified issuer.
7. audience or authorized API context.
8. roles: normalized application roles.
9. permissions: derived server-side permissions or a permission-evaluation reference.
10. service_identity: verified service name for service callers.
11. calling_service: authenticated direct caller.
12. on_behalf_of_subject: verified human subject when a service acts on behalf of a user.
13. authentication_method.
14. authentication_time.
15. assurance level where available.
16. session identifier reference, never the raw cookie.
17. correlation identifier.
18. request identifier.
19. workspace identifier fixed to the single supported workspace, if required by existing interfaces.
20. claim-mapping version.
21. permission-policy version.

Identity rules:

1. Never construct normalized identity from external actor or role headers.
2. Never accept external subject, email, role, permission, service, or forwarding headers as authoritative.
3. Never permit the browser to select its own effective role.
4. Never let display name or email replace the stable subject identifier as the security key.
5. Never let an internal service erase its own identity when acting on behalf of a user.
6. Owner services must know both the authenticated calling service and the represented human identity where applicable.
7. Unknown or unmapped roles must grant no privileged permission.
8. Unknown claims must not automatically become roles.
9. Role mapping must be issuer-specific and configuration-controlled.
10. Identity context must be immutable after authentication within a request.
11. Identity context must be available to audit logic without re-reading untrusted headers.
12. Identity context must be propagated only through authenticated internal channels.

Claim and role mapping

Define a centralized claim-mapping and role-mapping policy.

Required human roles:

1. viewer
2. analyst
3. governance_reviewer
4. administrator

Required named service identities must be enumerated explicitly, including at minimum:

1. gateway
2. authorized worker identities
3. reporting service if applicable
4. callback processor if applicable
5. metrics collector if applicable
6. migration or maintenance identity if applicable
7. any owner-service-specific worker identity
8. any scheduled job identity

Mapping requirements:

1. Map provider claims to internal roles using explicit configuration.
2. Do not use arbitrary token role names directly throughout the application.
3. Normalize provider-specific group or role claims.
4. Reject or ignore unknown role values.
5. Define required claims by issuer.
6. Define required email verification policy.
7. Define behavior for missing email.
8. Define behavior for missing subject.
9. Define behavior for missing group or role claims.
10. Define behavior for disabled users.
11. Define role-removal propagation.
12. Define session invalidation or refresh when roles change.
13. Define maximum role-mapping cache duration.
14. Define whether role mapping is evaluated at login, per request, or by short-lived policy cache.
15. Privileged roles must not remain effective indefinitely after removal at the identity provider.
16. Mapping changes must be versioned and auditable.
17. Production role mapping must not be editable by unprivileged users.
18. Local test-role mapping must be isolated from staging and production configuration.
19. Every permission must be derived from the centralized policy, not directly from raw provider claims.

Centralized server-side RBAC

Implement one authoritative permission model for all application paths.

Do not scatter role-name conditionals throughout routers, service methods, templates, or repositories.

Create a central policy representation that maps:

1. Human roles to permissions.
2. Named service identities to permissions.
3. Permissions to operations.
4. Permissions to resource types.
5. Permissions to governance fields.
6. Permissions to bulk actions.
7. Permissions to system endpoints.
8. Permissions to metrics and documentation exposure.
9. Permissions to owner-service APIs.
10. Permissions to background and event-driven operations.
11. Permissions requiring step-up authentication.
12. Permissions requiring recent authentication.
13. Permissions requiring a specific direct calling service.
14. Permissions that allow acting on behalf of a user.
15. Permissions that require row-level constraints.

Minimum human role intent

viewer:

1. Read only approved non-restricted information.
2. No mutations.
3. No bulk operations.
4. No governance-restricted fields.
5. No administrative or service-management endpoints.
6. No unrestricted metrics or documentation unless explicitly approved.
7. No owner-service direct access.

analyst:

1. Read information permitted for analysts.
2. Perform explicitly allowed analysis mutations.
3. Perform explicitly allowed source or workflow actions.
4. No governance-only fields unless separately permitted.
5. No administrative operations.
6. No unrestricted bulk or destructive operations unless specifically granted.
7. No owner-service direct access.

governance_reviewer:

1. Read governance-restricted information where allowed.
2. Review, approve, reject, or annotate governance records where allowed.
3. No general administration unless separately granted.
4. Sensitive governance actions may require recent or stronger authentication.
5. No owner-service direct access.

administrator:

1. Perform documented administrative operations.
2. Manage approved security and application settings.
3. Access explicitly approved system endpoints.
4. Access metrics and documentation only according to production policy.
5. Perform high-risk actions only with required step-up authentication.
6. No automatic database or service bypass beyond explicitly defined permissions.
7. No direct owner-service access unless the architecture explicitly requires and permits it.

Named services:

1. Receive only narrowly scoped permissions.
2. Must not inherit human administrator permissions.
3. Must not use generic internal-trusted status as permission.
4. Must authenticate independently.
5. Must be restricted by audience.
6. Must be restricted by direct caller identity.
7. Must be restricted by operation.
8. Must be restricted by row-level policy where applicable.
9. Must not impersonate users unless explicitly authorized.
10. Must preserve calling service and represented user identity in audit events.

Permission coverage

The centralized permission model must cover every exposed and non-HTTP privileged path, including:

1. Console pages.
2. Console API calls.
3. Gateway routes.
4. Owner-service routes.
5. Public API routes.
6. Internal API routes.
7. Read operations.
8. Create operations.
9. Update operations.
10. Delete operations.
11. Bulk actions.
12. Source actions.
13. Import operations.
14. Export operations.
15. Reporting.
16. Governance fields.
17. Governance actions.
18. Callback endpoints.
19. Event endpoints.
20. Metrics endpoints.
21. Documentation endpoints.
22. OpenAPI schema endpoints.
23. Health endpoints.
24. Readiness endpoints.
25. Liveness endpoints.
26. System endpoints.
27. Administrative endpoints.
28. Background jobs.
29. Queue consumers.
30. Scheduled jobs.
31. Worker operations.
32. Command-line administrative utilities.
33. Database maintenance functions exposed to application roles.
34. WebSocket or streaming endpoints if present.
35. Temporary download links.
36. Object-storage access paths.
37. Search-index access.
38. Cached result access.
39. Reporting replicas or alternate data stores.
40. Audit-data access.
41. Session-management endpoints.
42. Security-configuration endpoints.
43. Credential-management operations.

Permission matrix

Generate and maintain a machine-readable permission matrix for every route and protected operation.

The matrix must include:

1. HTTP method where applicable.
2. Route path.
3. Route name.
4. Owning service.
5. Operation identifier.
6. Resource type.
7. Required authentication type.
8. Allowed human roles.
9. Allowed service identities.
10. Required permission.
11. Required direct calling service.
12. Whether acting on behalf of a user is allowed.
13. Whether row-level security applies.
14. Whether governance fields are involved.
15. Whether step-up authentication is required.
16. Whether recent authentication is required.
17. Expected unauthenticated response.
18. Expected authenticated-but-denied response.
19. Required audit behavior.
20. Production exposure policy.
21. Rate-limit policy.
22. Request-size policy.
23. CSRF requirement.
24. CORS relevance.
25. Test identifiers covering the route.

Requirements:

1. Every exposed route must appear in the matrix.
2. Every protected non-route operation must appear in the matrix or an equivalent operation matrix.
3. CI must fail if a new route lacks a matrix entry.
4. CI must fail if a matrix entry references a missing route or operation.
5. Automated tests must verify the matrix against actual authorization behavior.
6. The matrix must be generated or validated from authoritative source data.
7. Documentation must include a human-readable version.
8. The matrix must not rely solely on route-name conventions.
9. Metrics, documentation, health, system, and callback endpoints must be included.
10. Denied and allowed expectations must be tested for all applicable roles and service identities.

External identity-header rejection

At all public and browser-facing boundaries:

1. Reject or remove X-Actor.
2. Reject or remove X-Operator-Role.
3. Reject or remove X-Subject.
4. Reject or remove X-User.
5. Reject or remove X-Email.
6. Reject or remove X-Roles.
7. Reject or remove X-Permissions.
8. Reject or remove X-Service-Identity.
9. Reject or remove X-Forwarded-Actor.
10. Reject or remove any legacy identity, role, operator, or forwarding headers.
11. Ensure these headers cannot influence authentication.
12. Ensure these headers cannot influence authorization.
13. Ensure these headers cannot influence audit identity.
14. Ensure these headers cannot influence row-level security context.
15. Ensure proxy behavior does not preserve untrusted versions of internal identity headers.
16. Define one controlled internal header namespace if internal forwarding headers remain necessary.
17. Strip the internal namespace at the first trusted ingress boundary.
18. Recreate internal identity propagation only after authentication.

Service-to-service authentication

All service-to-service calls must authenticate the direct calling workload.

Select and document one production-supported model, such as:

1. Mutual TLS using workload certificates.
2. Private-key JWT client authentication.
3. Short-lived JWT workload identity.
4. Platform-native workload identity.
5. Another approved cryptographic workload identity.

The chosen model must define:

1. Credential issuer.
2. Credential subject.
3. Credential audience.
4. Allowed signing algorithms.
5. Credential lifetime.
6. Key storage.
7. Key rotation.
8. Revocation.
9. Replay controls.
10. Workload binding.
11. Environment binding.
12. Service-name normalization.
13. Trust roots.
14. Failure behavior.
15. Deployment configuration.
16. Local-development behavior.
17. Test credentials.
18. Staging validation.
19. Audit fields.
20. Incident-response procedure.

Service-token requirements:

1. Use short-lived credentials.
2. Validate signature.
3. Validate issuer.
4. Validate audience.
5. Validate subject.
6. Validate expiry.
7. Validate not-before.
8. Validate required service claims.
9. Validate allowed algorithm.
10. Reject credentials intended for another service.
11. Reject generic unscoped internal tokens.
12. Do not use static shared bearer tokens as the production design.
13. Do not log service credentials.
14. Do not pass service credentials to browsers.
15. Do not store service credentials in source control.
16. Rotate service credentials safely.
17. Support revocation or rapid expiry after compromise.
18. Grant only named service permissions.

Gateway and owner-service trust

Owner APIs must accept calls only from:

1. The authenticated gateway.
2. Explicitly authorized named workers.
3. Other specifically documented service identities.

Owner APIs must not accept:

1. Direct browser calls.
2. Direct external user bearer tokens unless explicitly designed and documented.
3. Anonymous calls.
4. Calls authenticated only by network location.
5. Calls authenticated only by an identity header.
6. Calls from arbitrary internal services.
7. Calls from services with the wrong audience.
8. Calls from services without the required operation permission.

When the gateway acts on behalf of a human user:

1. The owner service must authenticate the gateway as the direct caller.
2. The owner service must receive or reconstruct a verified on-behalf-of user context.
3. The owner service must retain both identities.
4. The owner service must enforce permissions applicable to the represented user.
5. The owner service must enforce permissions applicable to the gateway.
6. The owner service must reject unauthorized impersonation.
7. The owner service must audit both calling service and represented user.
8. The represented user context must be integrity protected.
9. The owner service must not treat forwarded user identity as direct user authentication.

Internal identity propagation

If identity context is forwarded between trusted services:

1. Use an authenticated and encrypted channel.
2. Bind the propagated identity to the authenticated calling service.
3. Protect the context from modification.
4. Protect the context from replay.
5. Use short-lived propagation data.
6. Include intended audience.
7. Include issued-at and expiry.
8. Include a unique identifier where replay detection is required.
9. Include verified subject.
10. Include normalized roles or policy reference.
11. Include calling service.
12. Include on-behalf-of subject where applicable.
13. Include authentication time and method when required.
14. Include correlation identifier.
15. Do not forward raw OIDC tokens unless explicitly required and approved.
16. Do not forward arbitrary provider claims.
17. Do not accept propagation context from untrusted callers.
18. Revalidate the propagation mechanism at every service boundary.
19. Strip externally supplied versions of internal propagation headers.
20. Prefer a signed internal identity envelope or equivalent cryptographic mechanism over plain headers.

Row-level security

Sprint 25 must explicitly implement database-enforced row-level security for security-sensitive tables.

RLS applies where records differ by:

1. Governance visibility.
2. Security classification.
3. User ownership.
4. User assignment.
5. Analyst assignment.
6. Service ownership.
7. Worker queue assignment.
8. Record lifecycle state.
9. Source restriction.
10. Sensitive-data designation.
11. Authorized operation.
12. Audit visibility.
13. Any other row-specific access rule.

RLS design principles:

1. RLS is defense in depth.
2. RLS does not replace API permission checks.
3. API authorization determines whether an operation is allowed.
4. RLS determines which rows the allowed operation may read or affect.
5. RLS must default deny when no policy applies.
6. Missing database identity context must deny access.
7. Unknown roles or services must deny access.
8. Database context must come only from verified normalized identity.
9. Database context must never come directly from request headers, query parameters, form data, browser data, or unverified token claims.
10. Human and service identities must be distinguishable.
11. Governance access must be explicit.
12. Bulk operations must remain constrained by RLS.
13. Direct repository calls must remain constrained by RLS.
14. Background workers must be constrained by service-specific policies.
15. Audit access must be constrained by dedicated policies.
16. Production application connections must not bypass RLS.

Database-role requirements

The production application must not connect as:

1. Database superuser.
2. Table owner for RLS-protected tables.
3. A role with BYPASSRLS.
4. An unrestricted maintenance role.
5. A shared role used for both migrations and runtime traffic.

Use separate roles for:

1. Schema migrations.
2. Runtime application queries.
3. Background workers where needed.
4. Read-only reporting where needed.
5. Administrative maintenance.
6. Audit access.
7. Local test setup.

Requirements:

1. Runtime roles must be least privilege.
2. Migration roles must not be used by normal application requests.
3. Sensitive tables should use FORCE ROW LEVEL SECURITY where appropriate.
4. Production-role behavior must be tested using the same privilege shape as production.
5. Tests must prove the runtime role cannot bypass RLS.
6. Views, functions, and procedures must be reviewed for security-definer behavior.
7. Security-definer functions must be narrowly scoped and explicitly justified.
8. No general-purpose function may bypass RLS for untrusted input.
9. Stored procedures must perform their own authorization where appropriate.
10. Reporting roles must not bypass row restrictions unless explicitly approved.

Database identity context

Set database identity context transactionally.

Requirements:

1. Start a database transaction for request-scoped work.
2. Set identity context using transaction-scoped settings.
3. Use SET LOCAL or an equivalent transaction-local mechanism.
4. Include only normalized verified values.
5. Include subject.
6. Include identity type.
7. Include calling service where applicable.
8. Include on-behalf-of subject where applicable.
9. Include relevant permission or policy version.
10. Include governance access flag only when derived from verified permission.
11. Include correlation identifier where useful.
12. Clear context automatically at transaction end.
13. Never use persistent connection-level context for request identity.
14. Prevent context leakage across pooled connections.
15. Prevent one request from inheriting another request’s identity.
16. Ensure rollback clears transaction-scoped context.
17. Ensure exception paths clear context.
18. Ensure background jobs set their own verified context.
19. Ensure migrations do not accidentally depend on runtime context.
20. Fail closed when context setup fails.

Example conceptual context:

BEGIN;
SET LOCAL app.identity_type = 'human';
SET LOCAL app.subject = 'verified-subject';
SET LOCAL app.calling_service = 'gateway';
SET LOCAL app.permissions = 'findings.read,governance.read';
SET LOCAL app.correlation_id = 'request-correlation-id';
-- authorized queries
COMMIT;

Do not copy this example blindly if the database access layer requires another safe implementation.

RLS policy requirements

Create explicit policies for:

1. SELECT.
2. INSERT.
3. UPDATE.
4. DELETE.
5. Restricted governance rows.
6. Assigned analyst rows.
7. Service-owned work queues.
8. Audit records.
9. Sensitive source records.
10. Any table identified by the data-classification review.

Policies must:

1. Default deny.
2. Check verified context.
3. Distinguish user and service access.
4. Prevent unauthorized row creation.
5. Prevent changing a row into an unauthorized state.
6. Prevent updates that move a row outside the caller’s allowed scope.
7. Prevent bulk operations from affecting unauthorized rows.
8. Prevent restricted rows from appearing through ordinary reads.
9. Prevent worker services from reading unrelated queues.
10. Prevent unauthorized audit access.
11. Be testable independently of HTTP routes.
12. Be documented in the architecture and database documentation.

RLS scope review

Review and document whether equivalent protections are required for:

1. Database views.
2. Materialized views.
3. Search indexes.
4. Caches.
5. Reporting replicas.
6. Data warehouses.
7. Object storage.
8. Export files.
9. Temporary download URLs.
10. Background-generated reports.
11. Event payloads.
12. Queue messages.
13. Snapshot tables.
14. Analytics tables.
15. Audit archives.

RLS does not automatically secure these paths. Each path must preserve equivalent authorization semantics.

CSRF protection

Implement explicit CSRF protection for browser-authenticated state-changing operations.

Requirements:

1. Protect POST, PUT, PATCH, DELETE, and other state-changing methods.
2. Protect logout.
3. Protect session-management operations.
4. Protect step-up initiation where applicable.
5. Bind CSRF tokens to the authenticated session.
6. Use cryptographically random CSRF tokens.
7. Validate origin for browser requests where applicable.
8. Validate Sec-Fetch-Site or equivalent fetch metadata where appropriate.
9. Reject unsafe cross-site form submissions.
10. Do not rely only on SameSite cookies.
11. Define accepted content types for state-changing endpoints.
12. Avoid accepting form-compatible content types for JSON-only APIs unless required.
13. Prevent login CSRF.
14. Ensure callback state validation remains separate from normal CSRF protection.
15. Do not log CSRF tokens.
16. Rotate or invalidate CSRF state when sessions rotate.
17. Include browser tests for valid and invalid CSRF behavior.
18. Provide a clear denied UX without exposing sensitive details.

Secure response headers

Set explicit production response headers, including as applicable:

1. Content-Security-Policy.
2. X-Content-Type-Options: nosniff.
3. Referrer-Policy.
4. Permissions-Policy.
5. Strict-Transport-Security at the appropriate ingress or application layer.
6. Frame-ancestors through CSP.
7. Cache-Control for authenticated and sensitive responses.
8. Pragma or equivalent legacy controls only where required.
9. Cross-Origin-Opener-Policy where compatible.
10. Cross-Origin-Resource-Policy where compatible.
11. Cross-Origin-Embedder-Policy only if compatible and required.

Requirements:

1. Do not use unsafe-inline or unsafe-eval without explicit justification.
2. Do not allow framing unless explicitly required.
3. Do not cache authenticated sensitive pages in shared caches.
4. Do not expose tokens or codes through referrer headers.
5. Document which layer owns each header.
6. Test headers in browser and integration tests.
7. Ensure error responses receive appropriate headers.

CORS

Implement restrictive CORS for browser-accessible APIs.

Requirements:

1. Use an explicit origin allowlist.
2. No wildcard origin with credentials.
3. Allow only required methods.
4. Allow only required request headers.
5. Expose only required response headers.
6. Configure credential behavior explicitly.
7. Separate local-development origins from staging and production.
8. Fail deployment validation if production origins are missing or unsafe.
9. Do not treat CORS as authentication or authorization.
10. Non-browser clients must still authenticate normally.
11. Test allowed and denied origins.
12. Test preflight behavior.
13. Test credentialed requests.
14. Ensure internal service endpoints do not become browser-accessible accidentally.

TLS and ingress

Production and staging traffic must use TLS.

Requirements:

1. Define the trusted TLS termination point.
2. Enforce HTTPS redirects where appropriate.
3. Configure HSTS.
4. Trust forwarded-protocol headers only from known ingress infrastructure.
5. Strip untrusted forwarded headers at ingress.
6. Prevent external clients from spoofing internal network or scheme metadata.
7. Use TLS for service-to-service traffic where the platform supports it.
8. Use mTLS if selected as the service-authentication mechanism.
9. Document certificate rotation.
10. Document trust roots.
11. Define behavior for expired or invalid certificates.
12. Ensure secure cookies are not issued over untrusted HTTP in staging or production.
13. Local HTTP exceptions must be explicitly limited to local development.

Request-size limits

Implement request-size limits.

Requirements:

1. Define a default request-body limit.
2. Define explicit exceptions for approved upload endpoints.
3. Limit individual field sizes where appropriate.
4. Limit header sizes.
5. Limit cookie sizes.
6. Limit query-string size.
7. Limit multipart part count.
8. Limit uploaded file count.
9. Reject oversized bodies before expensive parsing where possible.
10. Return a consistent safe error.
11. Do not include request bodies in security logs.
12. Test boundary, oversized, malformed, and chunked requests.
13. Configure matching limits at ingress and application layers.
14. Document endpoint-specific exceptions.

Rate limiting

Implement endpoint-specific rate limits.

At minimum cover:

1. Login initiation.
2. OIDC callback failures where appropriate.
3. Session status.
4. Logout.
5. Step-up authentication.
6. Email-code send requests when controlled by the application or provider integration.
7. Email-code verification when controlled by the application or provider integration.
8. Public API endpoints.
9. Expensive read endpoints.
10. Mutation endpoints.
11. Bulk operations.
12. Export endpoints.
13. Metrics endpoints.
14. Documentation endpoints if exposed.
15. Owner-service endpoints.
16. Audit-query endpoints.
17. Repeated denied privileged operations.

Rate-limit design must define:

1. Limit key.
2. User key.
3. Service key.
4. IP or network key.
5. Endpoint class.
6. Burst allowance.
7. Sustained rate.
8. Retry response.
9. Distributed behavior.
10. Proxy-awareness.
11. Fail-open or fail-closed behavior.
12. Storage failure behavior.
13. Exemptions.
14. Administrative override policy.
15. Metrics and alerts.
16. Test coverage.

Do not permit unauthenticated denial traffic to exhaust audit storage or application capacity.

Metrics, documentation, and system endpoint policy

Define an explicit production exposure policy for:

1. Metrics.
2. OpenAPI schema.
3. Swagger or interactive docs.
4. ReDoc or equivalent docs.
5. Health.
6. Readiness.
7. Liveness.
8. Version.
9. Build metadata.
10. Debug endpoints.
11. Profiling endpoints.
12. Internal diagnostics.
13. Configuration inspection.
14. System status.

Requirements:

1. No endpoint is public by accident.
2. Liveness may expose only minimal status.
3. Readiness must not expose secrets or sensitive dependency details.
4. Metrics must be internal-only or permission-protected.
5. Documentation must be disabled publicly or protected according to policy.
6. Debug and profiling endpoints must be disabled in production unless explicitly approved.
7. Build and version endpoints must not expose sensitive environment or dependency information.
8. All endpoints must appear in the permission matrix.
9. All endpoints must have explicit rate-limit and exposure policies.
10. Helm defaults must enforce the production policy.

401 and 403 semantics

Use consistent authentication and authorization responses.

401 Unauthorized means:

1. No credential was supplied where required.
2. The credential is malformed.
3. The credential is expired.
4. The credential is not yet valid.
5. The credential signature is invalid.
6. The issuer is invalid.
7. The audience is invalid.
8. The session is missing.
9. The session is expired.
10. The session is revoked.
11. Service authentication failed.

403 Forbidden means:

1. Authentication succeeded.
2. The normalized identity is valid.
3. The caller lacks the required permission.
4. The caller lacks the required role.
5. The calling service is not allowed.
6. Step-up authentication is required but not satisfied, unless a dedicated reauthentication response is defined.
7. The caller is authenticated but the requested operation is forbidden.

Additional requirements:

1. Do not reveal whether a protected resource exists when that would leak sensitive information.
2. Ensure browser UX distinguishes expired login from denied permission.
3. Keep API response bodies consistent and redacted.
4. Include correlation identifiers.
5. Do not include token-validation internals.
6. Audit denied privileged operations.
7. Do not audit every harmless unauthenticated probe as a privileged denial unless policy requires it.
8. Define whether selected resource-level denials return 403 or 404 to avoid information leakage.

Security audit requirements

Audit allowed and denied privileged actions.

Audit records must include only necessary information, such as:

1. Timestamp.
2. Correlation identifier.
3. Request identifier.
4. Verified human subject.
5. Verified service identity.
6. Calling service.
7. On-behalf-of subject where applicable.
8. Authentication method.
9. Permission evaluated.
10. Operation.
11. Resource type.
12. Safe resource identifier.
13. Authorization outcome.
14. Database outcome where relevant.
15. Denial category.
16. Policy version.
17. Claim-mapping version.
18. Source service.
19. Environment.
20. Safe network metadata where approved.
21. Step-up status where relevant.

Audit records must not contain:

1. Access tokens.
2. ID tokens.
3. Refresh tokens.
4. Authorization codes.
5. Email one-time codes.
6. Session cookies.
7. Raw session identifiers.
8. CSRF tokens.
9. Client secrets.
10. Private keys.
11. Raw Authorization headers.
12. Raw Cookie headers.
13. Full unfiltered provider claims.
14. Sensitive request bodies.
15. Secrets embedded in query strings.
16. Unnecessary personal data.

Audit behavior:

1. Audit privileged successes.
2. Audit privileged denials.
3. Audit administrator changes.
4. Audit governance decisions.
5. Audit bulk and destructive operations.
6. Audit service-identity failures where security relevant.
7. Audit session revocation.
8. Audit role or permission mapping changes.
9. Audit emergency access.
10. Audit security configuration changes.
11. Ensure spoofed identity headers cannot change audit identity.
12. Ensure audit events are traceable through correlation identifiers.
13. Protect audit storage with access controls.
14. Define retention.
15. Define integrity protections.
16. Define operational monitoring.
17. Define behavior when audit storage is unavailable.
18. Avoid allowing attackers to exhaust storage through repeated denials.
19. Apply rate limiting, aggregation, or deduplication where appropriate without losing important security evidence.
20. Sanitize attacker-controlled fields.
21. Prevent log injection.
22. Separate security audit from ordinary debug logging.
23. Test redaction.

Local and test authentication backend

A local role-selection or test authentication backend may remain only under strict controls.

Requirements:

1. It must be explicitly designated local or test only.
2. It must be disabled by default.
3. It must require an explicit local environment mode.
4. It must be technically impossible to start in staging or production.
5. Helm templates must reject it in staging and production.
6. Deployment validation must reject it in staging and production.
7. Runtime startup must reject it in staging and production.
8. It must not share configuration names with production OIDC.
9. It must not accept caller-supplied role headers.
10. It must create a normalized test identity through a controlled test mechanism.
11. It must not be reachable through production ingress.
12. Tests must prove production startup fails when local auth is selected.
13. Documentation must clearly label it non-production.
14. Demo role controls must not be rendered in staging or production console builds.

Account lifecycle, recovery, and bootstrap

Define:

1. First-administrator bootstrap.
2. Administrator role assignment.
3. User disablement.
4. User re-enablement.
5. Role removal.
6. Session revocation after role changes.
7. Account recovery.
8. Email-address change behavior.
9. Identity-provider outage behavior.
10. Lost-email-access behavior.
11. Emergency or break-glass access.
12. Break-glass credential storage.
13. Break-glass activation.
14. Break-glass expiry.
15. Break-glass audit requirements.
16. Break-glass post-use review.
17. Break-glass session limitations.
18. Recovery-contact requirements.
19. Deprovisioning.
20. Service-account decommissioning.

Requirements:

1. No undocumented permanent administrator credential.
2. No shared administrator account.
3. Break-glass access must be narrowly scoped.
4. Break-glass use must be strongly audited.
5. Break-glass credentials must not bypass all controls silently.
6. Role removal must take effect within a documented bounded period.
7. Disabled users must lose active sessions.
8. Decommissioned services must lose credentials and permissions.
9. Recovery must not rely solely on caller-provided email claims.
10. Bootstrap must be safe in automated deployment.

Data persistence

Persist only necessary session and security-audit state.

Do not persist:

1. Raw access tokens unless explicitly required.
2. Raw ID tokens.
3. Raw authorization codes.
4. Raw email one-time codes.
5. Raw session cookies.
6. Raw CSRF tokens.
7. Unnecessary identity-provider claims.
8. Full authentication responses.
9. Provider secrets in application tables.
10. Unredacted security headers.

If refresh tokens are unavoidable:

1. Store only server-side.
2. Encrypt at rest.
3. Restrict access.
4. Rotate on use where supported.
5. Revoke on logout or compromise where supported.
6. Exclude from logs and audit.
7. Define retention.
8. Define key rotation.
9. Define incident response.
10. Justify the need in architecture documentation.

Middleware and enforcement architecture

Implement application-wide middleware or equivalent framework-level enforcement for:

1. Request correlation.
2. Trusted proxy handling.
3. External identity-header stripping.
4. Authentication.
5. Session lookup.
6. JWT validation.
7. Service authentication.
8. Normalized identity creation.
9. CSRF validation.
10. Permission evaluation.
11. Step-up enforcement.
12. Request-size enforcement.
13. Rate limiting.
14. Security response headers.
15. Audit context.
16. Consistent error handling.

Requirements:

1. Avoid router-specific custom authentication logic unless explicitly justified.
2. Avoid duplicated role checks.
3. Avoid direct raw-token parsing in business handlers.
4. Avoid direct provider-claim access in business handlers.
5. Require protected routes to declare their permission.
6. Fail tests when a route lacks declared security metadata.
7. Make public routes explicit.
8. Make service-only routes explicit.
9. Make browser-session routes explicit.
10. Make JWT API routes explicit.
11. Make row-level-security requirements explicit.
12. Preserve authorization checks in service methods for non-HTTP callers.
13. Ensure background jobs invoke the same permission or operation policy where applicable.

Testing requirements

Verification must explicitly cover:

1. Unit tests.
2. Database tests.
3. Integration tests.
4. Public API contract tests.
5. Event contract tests.
6. Browser and operator UI tests.
7. Deployment and Helm tests.
8. Bounded staging tests.
9. Bounded live-provider tests.
10. Security-negative tests.
11. Permission-matrix tests.
12. RLS tests.
13. Audit-redaction tests.
14. Service-authentication tests.
15. Session-lifecycle tests.
16. Rate-limit tests.
17. Request-size tests.
18. Header and CORS tests.

Ordinary CI requirements:

1. CI must remain deterministic.
2. CI must not depend on a live external identity provider.
3. Use local cryptographic test issuers, fixed test keys, controlled clocks, and deterministic metadata fixtures.
4. Key-rotation tests must be deterministic.
5. Browser tests must use a deterministic fake or local OIDC provider.
6. Live-provider tests must be separated from ordinary CI.
7. Any inapplicable test layer must be justified in the test plan.
8. No layer may be silently omitted.

JWT and OIDC negative tests

Test at minimum:

1. Missing token.
2. Empty token.
3. Malformed token.
4. Truncated token.
5. Invalid base64.
6. Invalid JSON.
7. Missing signature.
8. Invalid signature.
9. Wrong signing key.
10. Unknown key ID.
11. Key rotation.
12. Removed old key.
13. Wrong issuer.
14. Issuer formatting mismatch.
15. Wrong audience.
16. Multiple audiences without valid client binding.
17. Missing audience.
18. Expired token.
19. Future not-before.
20. Future issued-at outside allowed skew.
21. Missing subject.
22. Empty subject.
23. Missing required claims.
24. Wrong token type.
25. Disallowed algorithm.
26. none algorithm.
27. Algorithm-confusion attempt.
28. Untrusted JWKS location.
29. Untrusted issuer.
30. Replay where detectable.
31. Wrong nonce.
32. Missing nonce.
33. Wrong state.
34. Missing state.
35. Reused state.
36. Expired login transaction.
37. Wrong PKCE verifier.
38. Missing PKCE verifier.
39. Non-S256 PKCE.
40. Wrong redirect URI.
41. Callback to untrusted return path.
42. Token or code leakage in logs.
43. Provider metadata outage.
44. JWKS timeout.
45. Oversized JWKS response.
46. Excessive unknown-key refresh attempts.

Session tests

Test at minimum:

1. Session created after valid login.
2. Opaque cookie only.
3. Secure attribute in production.
4. HttpOnly attribute.
5. SameSite attribute.
6. Correct Path and Domain.
7. Idle timeout.
8. Absolute timeout.
9. Remembered-session timeout.
10. Session rotation after login.
11. Session rotation after step-up.
12. Old session invalid after rotation.
13. Logout invalidates server state.
14. Expired session returns 401.
15. Revoked session returns 401.
16. Account disablement invalidates sessions.
17. Role removal invalidates or refreshes sessions.
18. Session fixation prevention.
19. Session identifier absent from logs.
20. Cookie absent from logs.
21. Concurrent sessions.
22. Logout-all behavior if implemented.
23. Session cleanup.
24. Storage capacity and expiry behavior.
25. Browser cache behavior for authenticated pages.
26. Sensitive action requires recent authentication.

Passwordless and browser tests

Test at minimum:

1. Successful email-code login through the test provider.
2. Incorrect code.
3. Expired code.
4. Reused code.
5. Superseded code.
6. Too many attempts.
7. Too many send requests.
8. Unknown account behavior.
9. Delayed email flow.
10. Login CSRF.
11. Callback state validation.
12. Callback nonce validation.
13. PKCE validation.
14. Logout.
15. Session expiry.
16. Remembered session.
17. Viewer restrictions.
18. Analyst permissions.
19. Governance-only data.
20. Administrator step-up.
21. Denied UX.
22. Expired-session UX.
23. Open redirect prevention.
24. CSRF valid request.
25. CSRF missing token.
26. CSRF incorrect token.
27. CSRF cross-site request.
28. Secure response headers.
29. Demo-role UI absent in staging and production modes.

Spoofing tests

Prove that spoofed headers cannot affect authentication, authorization, audit, or RLS.

Test at minimum:

1. Spoofed X-Actor.
2. Spoofed X-Operator-Role.
3. Spoofed subject.
4. Spoofed email.
5. Spoofed roles.
6. Spoofed permissions.
7. Spoofed service identity.
8. Spoofed forwarded identity.
9. Duplicate trusted and untrusted header forms.
10. Mixed-case header forms.
11. Proxy-preserved header attempts.
12. Header injection.
13. Spoofed governance permission.
14. Spoofed database context.
15. Spoofed correlation metadata where security relevant.
16. Audit identity remains verified identity.
17. Permission result remains unchanged.
18. RLS-visible rows remain unchanged.

Permission-matrix tests

Generate and execute tests for every route and protected operation.

For each applicable human role and service identity, test:

1. Allowed access succeeds.
2. Denied access fails.
3. Unauthenticated access returns 401.
4. Authenticated-but-not-permitted access returns 403 or approved non-disclosing response.
5. Required audit event exists.
6. Governance fields are filtered correctly.
7. Row-level restrictions apply.
8. Step-up requirements apply.
9. Direct caller restrictions apply.
10. Owner-service restrictions apply.
11. Rate-limit class is configured.
12. Request-size policy is configured.
13. CSRF policy is configured where relevant.
14. Production exposure policy is defined.

Database and RLS tests

Test at minimum:

1. Missing database identity context denies access.
2. Viewer cannot read governance rows.
3. Viewer cannot mutate rows.
4. Analyst can read only permitted rows.
5. Analyst cannot update rows outside assignment or policy.
6. Governance reviewer can read permitted restricted rows.
7. Governance reviewer cannot perform administrator-only changes.
8. Administrator access matches explicit policy.
9. Worker can read only its authorized queue rows.
10. Worker cannot read another worker’s rows.
11. Gateway on-behalf-of access preserves both identities.
12. Bulk update cannot affect unauthorized rows.
13. Bulk delete cannot affect unauthorized rows.
14. Insert policy prevents unauthorized ownership or classification.
15. Update policy prevents moving a row into an unauthorized scope.
16. Runtime database role cannot bypass RLS.
17. Table-owner behavior is not used by runtime.
18. BYPASSRLS is absent from runtime role.
19. FORCE ROW LEVEL SECURITY behavior works where configured.
20. Context clears at transaction end.
21. Context clears after rollback.
22. Context clears after exception.
23. Connection-pool reuse does not leak identity.
24. Parallel requests do not leak context.
25. Repository-level direct calls remain constrained.
26. Views preserve restrictions.
27. Security-definer functions do not create unauthorized bypass.
28. Reporting paths preserve restrictions.
29. Export paths preserve restrictions.
30. Audit-table policies restrict access.
31. Spoofed request headers do not alter RLS context.

Service-authentication tests

Test at minimum:

1. Valid gateway identity accepted by owner service.
2. Valid authorized worker accepted.
3. Unauthenticated direct owner-service call rejected.
4. Browser session cannot directly call owner service.
5. Wrong service audience rejected.
6. Wrong service issuer rejected.
7. Wrong service signature rejected.
8. Expired service token rejected.
9. Future service token rejected.
10. Unknown service identity rejected.
11. Unauthorized internal service rejected.
12. Replayed service credential rejected where replay protection applies.
13. Calling service retained in normalized context.
14. On-behalf-of user retained separately.
15. Service cannot fabricate a different user.
16. Service cannot grant itself permissions.
17. Service credentials are absent from logs.
18. Credential rotation works.
19. Revoked or retired service credential fails.
20. Owner-service audit includes direct caller and represented user.

Audit tests

Test at minimum:

1. Allowed privileged operation creates audit event.
2. Denied privileged operation creates audit event.
3. Unauthenticated owner-service denial creates appropriate traceable security event according to policy.
4. Spoofed identity headers do not alter audit identity.
5. Correlation identifier is present.
6. Permission is present.
7. Resource is safely identified.
8. Outcome is present.
9. Denial category is safe.
10. Access token is absent.
11. ID token is absent.
12. Refresh token is absent.
13. Authorization code is absent.
14. Email code is absent.
15. Cookie is absent.
16. CSRF token is absent.
17. Raw Authorization header is absent.
18. Sensitive request body is absent.
19. Log-injection input is sanitized.
20. Audit flood controls work.
21. Audit-store failure behavior is tested.
22. Audit access permissions and RLS are tested.
23. Retention configuration is tested where feasible.

Deployment and Helm requirements

Add configuration and secret handling for:

1. OIDC issuer.
2. OIDC client ID.
3. OIDC client secret where required.
4. Redirect URIs.
5. Post-logout redirect URIs.
6. Trusted audiences.
7. Allowed algorithms.
8. Required claims.
9. Claim mappings.
10. Role mappings.
11. JWKS cache policy.
12. JWKS refresh policy.
13. OIDC metadata timeouts.
14. Session signing or encryption keys if applicable.
15. Session storage configuration.
16. Session idle timeout.
17. Session absolute timeout.
18. Remembered-session timeout.
19. Step-up recent-authentication window.
20. Service credential issuer.
21. Service audiences.
22. Service trust roots.
23. Service credential lifetimes.
24. Named service identities.
25. Internal propagation signing keys or trust configuration.
26. TLS and ingress settings.
27. Trusted proxy ranges.
28. Secure-cookie enforcement.
29. CORS origins.
30. Allowed CORS methods.
31. Allowed CORS headers.
32. Request-size limits.
33. Endpoint rate limits.
34. Metrics exposure.
35. Documentation exposure.
36. Health exposure.
37. Audit storage.
38. Audit retention.
39. RLS runtime database role.
40. Migration database role.
41. Worker database roles.
42. Local-auth enablement guard.
43. Environment identity.
44. Break-glass configuration if approved.

Deployment safety requirements:

1. Missing critical production security configuration must fail startup or deployment validation.
2. Local authentication in staging or production must fail deployment.
3. Wildcard production CORS with credentials must fail validation.
4. Missing session expiry must fail validation.
5. Unlimited session lifetime must fail validation.
6. HTTP-only production cookie misconfiguration must fail validation.
7. Insecure cookie settings must fail validation.
8. Unknown or unsafe JWT algorithm configuration must fail validation.
9. Missing issuer or audience must fail validation.
10. Runtime database superuser configuration must fail validation.
11. Runtime BYPASSRLS configuration must fail validation.
12. Runtime table-owner configuration for protected tables must fail validation.
13. Public metrics or docs exposure must require explicit opt-in.
14. Secrets must come from approved secret stores or Kubernetes secrets.
15. Secrets must not appear in rendered documentation examples as real values.
16. Helm README must explain rotation.
17. Helm tests must verify secure defaults.
18. Staging must resemble production security behavior.

Operational monitoring and incident response

Add monitoring for:

1. Login success and failure rates.
2. Email-code send and verification failures where visible.
3. Excessive login attempts.
4. Session creation and revocation.
5. JWT validation failures by category.
6. Service-authentication failures.
7. Unknown signing-key events.
8. JWKS refresh failures.
9. Permission denials.
10. Privileged denials.
11. RLS policy denials where observable.
12. Owner-service direct-call attempts.
13. Audit-storage failures.
14. Rate-limit activation.
15. Request-size rejections.
16. CSRF failures.
17. Suspicious role-mapping changes.
18. Break-glass use.
19. Repeated step-up failures.
20. Session-revocation failures.

Document incident procedures for:

1. OIDC provider outage.
2. OIDC signing-key rotation failure.
3. OIDC issuer compromise.
4. Client-secret compromise.
5. Session-store compromise.
6. Session-cookie theft.
7. Service credential compromise.
8. Internal propagation-key compromise.
9. Database-role compromise.
10. Audit-store outage.
11. Email-code abuse or mail bombing.
12. Unauthorized administrator assignment.
13. Break-glass activation.
14. Emergency session revocation.
15. Forced logout of all users.
16. Forced service-credential rotation.
17. Temporary disabling of privileged operations.

Documentation requirements

Update all affected documentation.

Required documents include:

1. Root README.
2. Architecture documentation.
3. Dashboard specification.
4. Operator runbook.
5. Gateway documentation.
6. Console documentation.
7. Owner-service documentation.
8. Worker documentation.
9. API authentication documentation.
10. Service-authentication documentation.
11. Database and RLS documentation.
12. Permission-matrix documentation.
13. Audit documentation.
14. Helm README.
15. Secrets guide.
16. Local-development guide.
17. Staging validation guide.
18. Incident-response procedures.
19. Account bootstrap and recovery guide.
20. Testing strategy.
21. Security limitations.
22. Production exposure policy for metrics, docs, and system endpoints.

Create an ADR covering:

1. Passwordless OIDC authentication.
2. Email-code assurance limitations.
3. Authorization Code flow.
4. PKCE.
5. State and nonce.
6. Browser session architecture.
7. Session expiry.
8. Session rotation.
9. Session revocation.
10. Logout behavior.
11. Claim mapping.
12. Role mapping.
13. Centralized RBAC.
14. Step-up authentication.
15. Service authentication.
16. On-behalf-of identity propagation.
17. Owner-service trust.
18. Row-level security.
19. Database roles.
20. Database transaction context.
21. Audit architecture.
22. Metrics and documentation exposure.
23. Local-auth isolation.
24. Recovery and break-glass behavior.
25. Security trade-offs.
26. Rejected alternatives.

Documentation must explicitly publish:

1. Login route.
2. Callback route.
3. Logout route.
4. Session-expiry behavior.
5. Reauthentication flow.
6. Normalized internal identity context.
7. Claim mapping.
8. Role mapping.
9. Permission model.
10. Permission matrix.
11. Scopes.
12. Audiences.
13. Issuers.
14. JWKS settings.
15. Session settings.
16. Service identities.
17. Service audiences.
18. Internal propagation format.
19. RLS tables and policy intent.
20. Database runtime roles.
21. 401 versus 403 semantics.
22. Audit schema.
23. Redaction rules.
24. Rate-limit policy.
25. Request-size policy.
26. CORS policy.
27. TLS expectations.
28. Production metrics policy.
29. Production documentation policy.
30. Local-development limitations.
31. Staging and live-provider validation process.

Apply Sprint 24 documentation requirements:

1. Complete scoped documentation updates.
2. Completion update.
3. Historical-research preservation.
4. Final consistency search.
5. Search for stale identity-header references.
6. Search for stale demo-role references.
7. Search for static-token assumptions.
8. Search for public metrics or docs assumptions.
9. Search for inconsistent role names.
10. Search for inconsistent permission names.
11. Search for outdated session behavior.
12. Search for owner-service direct-access assumptions.
13. Search for missing RLS documentation.
14. Ensure examples, environment variables, Helm values, code, tests, and docs use consistent names.

Implementation sequence

The Codex agent should produce a plan and implementation in a dependency-aware sequence.

Recommended sequence:

1. Inventory all routes, services, workers, event consumers, system endpoints, metrics, docs, database tables, views, exports, and privileged operations.
2. Generate the initial route and operation inventory.
3. Define normalized identity context.
4. Define permission names and centralized policy model.
5. Define role and service mappings.
6. Define authentication assurance and step-up requirements.
7. Define the permission matrix.
8. Define the RLS table inventory and policy intent.
9. Define database runtime and migration roles.
10. Implement external identity-header stripping.
11. Implement OIDC client and callback validation.
12. Implement deterministic local OIDC test provider or fixtures.
13. Implement secure server-side sessions.
14. Implement login, callback, logout, session, and reauthentication routes.
15. Implement application-wide authentication middleware.
16. Implement centralized authorization middleware and service-layer checks.
17. Implement service-to-service authentication.
18. Implement protected identity propagation.
19. Restrict owner services.
20. Implement RLS context setup.
21. Implement database RLS policies.
22. Implement CSRF.
23. Implement secure response headers.
24. Implement CORS.
25. Implement TLS and trusted-proxy behavior.
26. Implement request-size limits.
27. Implement rate limits.
28. Implement metrics, docs, health, and system endpoint policies.
29. Implement security auditing.
30. Remove or isolate demo-role behavior.
31. Generate and execute permission-matrix tests.
32. Add browser tests.
33. Add database and RLS tests.
34. Add service-auth tests.
35. Add deployment and Helm validation.
36. Add bounded staging and live-provider validation.
37. Update all documentation.
38. Run final consistency searches.
39. Produce a completion report mapping every acceptance criterion to code, test, and documentation evidence.

Required planning output from the Codex agent

Before implementation, the Codex agent must produce:

1. Current-state findings.
2. File and module inventory.
3. Route inventory.
4. Protected operation inventory.
5. Database table and view inventory.
6. Existing identity flow.
7. Existing session flow.
8. Existing service-auth flow.
9. Existing audit flow.
10. Existing deployment configuration.
11. Proposed architecture.
12. Proposed normalized identity context.
13. Proposed permission taxonomy.
14. Proposed role-to-permission mapping.
15. Proposed service-to-permission mapping.
16. Proposed permission matrix.
17. Proposed RLS policy matrix.
18. Proposed database-role model.
19. Proposed session model.
20. Proposed OIDC and passwordless flow.
21. Proposed service-authentication mechanism.
22. Proposed internal propagation mechanism.
23. Proposed CSRF model.
24. Proposed rate-limit model.
25. Proposed audit model.
26. Proposed migration plan.
27. Proposed test plan by layer.
28. Proposed documentation update list.
29. Risks and mitigations.
30. Rollout and rollback plan.
31. Explicit assumptions.
32. Any requirement that cannot be implemented in the existing architecture, with evidence and an alternative.

Acceptance criteria

Sprint 25 is complete only when all criteria below are satisfied.

Identity and login:

1. User identity is verified cryptographically through the trusted OIDC provider.
2. Passwordless email-code authentication works through the provider.
3. Authorization Code flow uses PKCE S256.
4. State and nonce are validated.
5. Callback replay fails.
6. Wrong callback transaction fails.
7. Browser receives only an opaque secure session cookie.
8. Raw provider tokens are not stored in browser-accessible storage.
9. Raw tokens, codes, and cookies do not appear in logs.
10. Sessions have idle and absolute expiry.
11. Remembered sessions remain bounded.
12. Sessions can be revoked server-side.
13. Logout invalidates the server-side session.
14. Role removal or user disablement invalidates or refreshes sessions within the documented bound.
15. Sensitive privileged actions support step-up authentication.

JWT validation:

1. Algorithm is explicitly allowed.
2. Signature is valid.
3. Issuer is valid.
4. Audience is valid.
5. Expiry is valid.
6. Not-before is valid.
7. Subject is valid.
8. Required claims are valid.
9. Wrong algorithm fails.
10. Wrong key fails.
11. Wrong issuer fails.
12. Wrong audience fails.
13. Malformed tokens fail.
14. Key rotation succeeds safely.
15. Metadata and JWKS failures fail closed.

Authorization:

1. All authorization is server-side.
2. One centralized permission model exists.
3. Every exposed route is in the permission matrix.
4. Every privileged non-route operation is represented.
5. Viewer restrictions are enforced.
6. Analyst permissions are enforced.
7. Governance reviewer permissions are enforced.
8. Administrator permissions are enforced.
9. Named service permissions are enforced.
10. Unknown roles and services default deny.
11. Client-side role selection does not affect authorization.
12. Spoofed actor or role headers do not affect authorization.
13. Consistent 401 and 403 semantics are implemented.

Service security:

1. Every service-to-service call is authenticated.
2. Owner services accept only gateway or explicitly authorized workers.
3. Direct unauthenticated owner-service calls fail.
4. Browser calls to owner services fail.
5. Wrong service audience fails.
6. Wrong service identity fails.
7. Calling service and represented user remain distinct.
8. Forwarded identity cannot be modified or spoofed.
9. Service credentials are short-lived or otherwise strongly protected.
10. Service credentials do not appear in logs.

Row-level security:

1. Security-sensitive tables have RLS.
2. Missing database identity context denies access.
3. Runtime database roles cannot bypass RLS.
4. Runtime roles are not superusers.
5. Runtime roles are not protected-table owners.
6. Runtime roles do not have BYPASSRLS.
7. Connection pooling does not leak identity context.
8. Viewer cannot read restricted rows.
9. Analyst cannot modify unauthorized rows.
10. Governance reviewer access matches policy.
11. Workers see only authorized rows.
12. Bulk operations remain constrained.
13. Direct repository calls remain constrained.
14. Audit access is constrained.
15. Equivalent authorization is preserved in exports, reports, caches, indexes, and alternate stores.

Browser and perimeter:

1. CSRF protection is enforced.
2. Login CSRF is prevented.
3. Logout is protected.
4. Secure headers are present.
5. CORS is restrictive.
6. TLS expectations are enforced.
7. Trusted proxy behavior is safe.
8. Request-size limits are enforced.
9. Rate limits are enforced.
10. Metrics exposure is explicit.
11. Documentation exposure is explicit.
12. Debug endpoints are disabled or explicitly protected.
13. Denied UX is clear and safe.
14. Session-expired UX is clear and safe.
15. Local/demo auth cannot start in staging or production.

Audit:

1. Privileged successes are audited.
2. Privileged denials are audited.
3. Every denied privileged operation creates a redacted traceable record.
4. Verified identity is recorded.
5. Calling service is recorded.
6. Represented user is recorded where applicable.
7. Permission is recorded.
8. Resource is recorded safely.
9. Correlation identifier is recorded.
10. Outcome is recorded.
11. Spoofed headers do not alter audit identity.
12. Tokens, codes, cookies, secrets, and unnecessary claims are absent.
13. Audit-flood controls exist.
14. Audit storage is access-controlled.
15. Audit failure behavior is documented and tested.

Tests and documentation:

1. Unit tests pass.
2. Integration tests pass.
3. Database and RLS tests pass.
4. Contract tests pass.
5. Browser tests pass.
6. Helm and deployment tests pass.
7. Deterministic CI passes without external provider access.
8. Bounded staging validation passes.
9. Bounded live-provider validation passes or is explicitly documented as blocked by an external dependency.
10. Every inapplicable test layer is justified.
11. Permission matrix is complete.
12. RLS policy matrix is complete.
13. Documentation is complete.
14. ADR is complete.
15. Final consistency search finds no stale demo identity, unsafe header trust, static-token, missing RLS, or contradictory security documentation.

Definition of done

The sprint is done when:

1. No external caller can assert its own identity or role.
2. Passwordless users authenticate through cryptographically verified OIDC.
3. Sessions are opaque, secure, bounded, rotated, revocable, and auditable.
4. Human and service identities are distinct and verified.
5. Every permission decision is server-side.
6. Every exposed route and privileged operation is represented in the permission model.
7. Owner services reject unauthorized direct access.
8. Database row-level security limits access to protected rows.
9. Runtime database identities cannot bypass RLS.
10. Privileged allowed and denied outcomes are safely auditable.
11. Tokens, authorization codes, email codes, cookies, secrets, and unnecessary claims are never logged.
12. Browser, API, service, database, deployment, and documentation requirements are all verified.
13. Production defaults fail closed.
14. Local or demo authentication is impossible to enable in staging or production.
15. The completion report links every acceptance criterion to implementation, test evidence, and documentation.
