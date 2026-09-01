from __future__ import annotations

import secrets
from dataclasses import replace
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ghostrecon.security.identity import AssuranceLevel, IdentityContext
from ghostrecon.security.jwt import TokenValidationError
from ghostrecon.security.oidc import OIDCTransaction, authorization_url, validate_return_path
from ghostrecon.security.policy import Permission, Role, authorize
from ghostrecon.security.sessions import (
    SESSION_COOKIE_NAME,
    TRANSACTION_COOKIE_NAME,
    csrf_token_for_session,
)

router = APIRouter(tags=["authentication"])


def _identity(request: Request) -> IdentityContext:
    identity = getattr(request.state, "identity", None)
    if identity is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return identity


async def _start(request: Request, *, purpose: str, return_path: str) -> RedirectResponse:
    settings = request.app.state.settings
    if settings.authentication_backend == "local_oidc":
        return RedirectResponse(validate_return_path(return_path), status_code=303)
    transaction = replace(
        OIDCTransaction.create(validate_return_path(return_path)),
        purpose=purpose,
        existing_session_id=(
            str(request.state.identity.session_id)
            if getattr(request.state, "identity", None) is not None
            else None
        ),
    )
    await request.app.state.oidc_transactions.put(transaction)
    metadata = await request.app.state.oidc_client.metadata()
    url = authorization_url(
        metadata,
        transaction,
        client_id=settings.oidc_client_id,
        redirect_uri=settings.oidc_redirect_uri,
    )
    if purpose == "step_up":
        url = f"{url}&{urlencode({'prompt': 'login', 'acr_values': 'phishing-resistant'})}"
    response = RedirectResponse(url, status_code=303)
    response.set_cookie(
        TRANSACTION_COOKIE_NAME,
        transaction.browser_binding,
        max_age=settings.oidc_transaction_ttl_seconds,
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/auth/login", operation_id="auth.login")
async def login(request: Request, return_path: str = Query(default="/")) -> RedirectResponse:
    return await _start(request, purpose="login", return_path=return_path)


@router.get("/auth/claims/refresh", operation_id="auth.claims.refresh")
async def refresh_claims(
    request: Request, return_path: str = Query(default="/")
) -> RedirectResponse:
    _identity(request)
    return await _start(request, purpose="claims_refresh", return_path=return_path)


@router.get("/auth/step-up", operation_id="auth.step_up")
async def step_up(request: Request, return_path: str = Query(default="/")) -> RedirectResponse:
    _identity(request)
    return await _start(request, purpose="step_up", return_path=return_path)


@router.get("/auth/callback", operation_id="auth.callback")
async def callback(
    request: Request,
    code: str = Query(min_length=1, max_length=4096),
    state: str = Query(min_length=1, max_length=256),
) -> RedirectResponse:
    settings = request.app.state.settings
    browser = request.cookies.get(TRANSACTION_COOKIE_NAME)
    try:
        transaction = await request.app.state.oidc_transactions.consume(
            state=state, browser_binding=browser or ""
        )
        token = await request.app.state.oidc_client.exchange_code(
            code=code,
            code_verifier=transaction.code_verifier,
            nonce=transaction.nonce,
        )
        claims = dict(token.claims)
        raw_roles = claims.get(settings.oidc_role_claim, [])
        if not isinstance(raw_roles, list) or not all(isinstance(item, str) for item in raw_roles):
            raise TokenValidationError("invalid provider role claim")
        provider_roles = frozenset(raw_roles)
        principal = await request.app.state.security_repository.provision_from_claims(
            claims,
            provider_roles=provider_roles,
            allow_create=False,
        )
        methods = set(claims.get("amr", [])) if isinstance(claims.get("amr"), list) else set()
        assurance = (
            AssuranceLevel.PHISHING_RESISTANT
            if methods & set(settings.oidc_phishing_resistant_amr)
            else AssuranceLevel.EMAIL_OTP
        )
        authenticated_at = datetime.fromtimestamp(int(claims.get("auth_time", claims["iat"])), UTC)
        created = await request.app.state.security_repository.create_session(
            principal,
            authentication_method=token.authentication_method,
            assurance=assurance,
            provider_roles=provider_roles,
            remembered=False,
            authenticated_at=authenticated_at,
        )
    except (KeyError, TypeError, ValueError, PermissionError, TokenValidationError) as exc:
        raise HTTPException(status_code=401, detail="OIDC callback rejected") from exc
    if transaction.existing_session_id:
        await request.app.state.security_repository.revoke(
            transaction.existing_session_id, reason=f"rotated_after_{transaction.purpose}"
        )
    response = RedirectResponse(transaction.return_path, status_code=303)
    response.delete_cookie(TRANSACTION_COOKIE_NAME, path="/")
    response.set_cookie(
        SESSION_COOKIE_NAME,
        created.secrets.identifier,
        max_age=int((created.absolute_expires_at - datetime.now(UTC)).total_seconds()),
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/auth/session", operation_id="auth.session.read")
async def session_details(request: Request) -> dict[str, object]:
    identity = _identity(request)
    settings = request.app.state.settings
    raw_session = request.cookies.get(SESSION_COOKIE_NAME)
    csrf = (
        csrf_token_for_session(raw_session, settings.session_hmac_key.encode())
        if raw_session and settings.session_hmac_key
        else "local-development-csrf"
    )
    return {
        "subject": identity.subject,
        "actor_label": identity.actor_label,
        "roles": sorted(identity.roles),
        "permissions": sorted(identity.permissions),
        "permitted_actions": sorted(identity.permissions),
        "assurance": identity.assurance.value,
        "authenticated_at": identity.authenticated_at.isoformat(),
        "claim_mapping_version": identity.claim_mapping_version,
        "permission_policy_version": identity.permission_policy_version,
        "csrf_token": csrf,
        "idle_expires_at": identity.attributes.get("idle_expires_at"),
        "absolute_expires_at": identity.attributes.get("absolute_expires_at"),
        "provider_roles_refreshed_at": identity.attributes.get("provider_roles_refreshed_at"),
    }


@router.get("/auth/sessions", operation_id="auth.sessions.list")
async def sessions(request: Request) -> dict[str, object]:
    identity = _identity(request)
    return {"sessions": [{"id": str(identity.session_id), "current": True}]}


@router.delete("/auth/sessions/{session_id}", operation_id="auth.sessions.revoke")
async def revoke_session(request: Request, session_id: str) -> JSONResponse:
    identity = _identity(request)
    if str(identity.session_id) != session_id:
        raise HTTPException(status_code=403, detail="step-up required for another session")
    await request.app.state.security_repository.revoke(session_id, reason="self_service")
    response = JSONResponse({"revoked": True})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.post("/auth/logout", operation_id="auth.logout")
async def logout(request: Request) -> JSONResponse:
    identity = _identity(request)
    await _require_csrf(request, identity)
    if identity.session_id:
        await request.app.state.security_repository.revoke(
            str(identity.session_id), reason="user_logout"
        )
    response = JSONResponse({"logged_out": True})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.post("/auth/logout-all", operation_id="auth.logout_all")
async def logout_all(request: Request) -> JSONResponse:
    identity = _identity(request)
    await _require_csrf(request, identity)
    await request.app.state.security_repository.revoke_subject(
        identity.subject, reason="subject_logout_all"
    )
    response = JSONResponse({"logged_out": True})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.get("/auth/provider-logout/callback", operation_id="auth.provider_logout.callback")
async def provider_logout_callback() -> RedirectResponse:
    return RedirectResponse("/", status_code=303)


def _principal_payload(principal: object) -> dict[str, object]:
    return {
        "id": principal.id,
        "subject": principal.subject,
        "actor_label": principal.actor_label,
        "email_verified": principal.email_verified,
        "disabled": principal.disabled,
        "role_ceiling": principal.role_ceiling,
        "mapping_version": principal.mapping_version,
        "policy_version": principal.policy_version,
    }


async def _require_admin(request: Request, *, csrf: bool = False) -> IdentityContext:
    identity = _identity(request)
    decision = authorize(
        identity,
        Permission.SECURITY_ADMIN,
        minimum_assurance=AssuranceLevel.PHISHING_RESISTANT,
        maximum_authentication_age_seconds=900,
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.code)
    if csrf:
        await _require_csrf(request, identity)
    return identity


@router.get("/v1/security/users", operation_id="security.users.list")
async def security_users(request: Request, limit: int = Query(default=100, ge=1, le=200)):
    await _require_admin(request)
    principals = await request.app.state.security_repository.list_principals(limit=limit)
    return {"users": [_principal_payload(item) for item in principals]}


@router.get("/v1/security/users/{principal_id}", operation_id="security.users.read")
async def security_user(request: Request, principal_id: str):
    await _require_admin(request)
    principal = await request.app.state.security_repository.get_principal(principal_id)
    if principal is None:
        raise HTTPException(status_code=404, detail="principal not found")
    return _principal_payload(principal)


@router.patch("/v1/security/users/{principal_id}", operation_id="security.users.manage")
async def security_user_update(
    request: Request,
    principal_id: str,
    body: Annotated[dict[str, object], Body()],
):
    actor = await _require_admin(request, csrf=True)
    roles = body.get("roles")
    reason = body.get("reason")
    version = body.get("mapping_version")
    disabled = body.get("disabled")
    if (
        not isinstance(roles, list)
        or not all(
            isinstance(role, str) and role in {item.value for item in Role} for role in roles
        )
        or not isinstance(reason, str)
        or not reason.strip()
        or not isinstance(version, str)
        or not isinstance(disabled, bool)
    ):
        raise HTTPException(status_code=422, detail="invalid principal update")
    try:
        principal = await request.app.state.security_repository.update_principal(
            principal_id,
            disabled=disabled,
            roles=frozenset(roles),
            expected_mapping_version=version,
            actor_subject=actor.subject,
            reason=reason,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail="principal version conflict") from exc
    if principal is None:
        raise HTTPException(status_code=404, detail="principal not found")
    return _principal_payload(principal)


@router.get(
    "/v1/security/users/{principal_id}/sessions",
    operation_id="security.users.sessions.list",
)
async def security_user_sessions(request: Request, principal_id: str):
    await _require_admin(request)
    if await request.app.state.security_repository.get_principal(principal_id) is None:
        raise HTTPException(status_code=404, detail="principal not found")
    records = await request.app.state.security_repository.principal_sessions(principal_id)
    return {
        "sessions": [
            {
                "id": item.id,
                "assurance": item.assurance,
                "created_at": item.created_at.isoformat(),
                "absolute_expires_at": item.absolute_expires_at.isoformat(),
                "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
            }
            for item in records
        ]
    }


@router.post(
    "/v1/security/users/{principal_id}/sessions/revoke",
    operation_id="security.users.sessions.revoke",
)
async def security_user_sessions_revoke(
    request: Request,
    principal_id: str,
    reason: Annotated[str, Body(embed=True, min_length=1, max_length=255)],
):
    await _require_admin(request, csrf=True)
    if await request.app.state.security_repository.get_principal(principal_id) is None:
        raise HTTPException(status_code=404, detail="principal not found")
    count = await request.app.state.security_repository.revoke_principal_sessions(
        principal_id, reason=reason
    )
    return {"revoked_sessions": count}


@router.get("/v1/security/audit", operation_id="security.audit.read")
async def security_audit(request: Request, limit: int = Query(default=100, ge=1, le=200)):
    identity = _identity(request)
    decision = authorize(
        identity,
        Permission.SECURITY_AUDIT_READ,
        minimum_assurance=AssuranceLevel.PHISHING_RESISTANT,
        maximum_authentication_age_seconds=900,
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.code)
    events = await request.app.state.security_repository.audit_events(limit=limit)
    return {
        "events": [
            {
                "id": item.id,
                "operation": item.operation,
                "decision": item.decision,
                "correlation_id": item.correlation_id,
                "created_at": item.created_at.isoformat(),
            }
            for item in events
        ]
    }


async def _proof(request: Request, purpose: str) -> dict[str, object]:
    identity = await _require_admin(request, csrf=True)
    proof = secrets.token_urlsafe(32)
    digest = __import__("hashlib").sha256(proof.encode()).hexdigest()
    stored = await request.app.state.security_redis.set(
        f"ghostrecon:security:{purpose}:{digest}", identity.subject, ex=60, nx=True
    )
    if not stored:
        raise HTTPException(status_code=503, detail="proof store unavailable")
    return {"proof": proof, "expires_in": 60, "purpose": purpose}


@router.post("/auth/bootstrap-proof", operation_id="auth.bootstrap_proof")
async def bootstrap_proof(request: Request):
    return await _proof(request, "bootstrap")


@router.post(
    "/v1/security/emergency-grants/proof",
    operation_id="security.emergency_grants.proof",
)
async def emergency_grant_proof(request: Request):
    return await _proof(request, "emergency-grant")


async def _require_csrf(request: Request, identity: IdentityContext) -> None:
    validator = getattr(request.app.state, "csrf_validator", None)
    if validator is not None and not await validator(request):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
