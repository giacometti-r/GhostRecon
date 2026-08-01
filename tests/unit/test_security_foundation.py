from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

from ghostrecon.security.identity import AssuranceLevel, IdentityContext, IdentityType
from ghostrecon.security.jwt import (
    TokenValidationError,
    obo_claims,
    service_claims,
    sign_eddsa,
    verify_eddsa,
)
from ghostrecon.security.oidc import (
    OIDCProviderMetadata,
    OIDCTransaction,
    authorization_url,
    discovery_url,
    validate_return_path,
    verify_oidc_id_token,
)
from ghostrecon.security.policy import Permission, authorize, permissions_for_roles
from ghostrecon.security.sessions import create_session_secrets, verify_secret


def _identity(
    *,
    roles: set[str],
    assurance: AssuranceLevel = AssuranceLevel.EMAIL_OTP,
    authenticated_at: datetime | None = None,
) -> IdentityContext:
    return IdentityContext(
        identity_type=IdentityType.HUMAN,
        subject="oidc|alice",
        actor_label="Alice",
        email_verified=True,
        issuer="https://login.example.test/",
        audience=("ghostrecon",),
        roles=frozenset(roles),
        permissions=permissions_for_roles(roles),
        calling_service=None,
        on_behalf_of_subject=None,
        authentication_method="email_otp",
        authenticated_at=authenticated_at or datetime.now(UTC),
        assurance=assurance,
        session_id=uuid4(),
        correlation_id="correlation",
        request_id="request",
        claim_mapping_version="mapping.v1",
        permission_policy_version="sprint25.v1",
        environment="test",
    )


def test_role_permissions_are_additive_and_unknown_roles_default_deny() -> None:
    analyst = permissions_for_roles({"analyst"})
    governance = permissions_for_roles({"governance_reviewer"})
    combined = permissions_for_roles({"analyst", "governance_reviewer", "unknown"})

    assert combined == analyst | governance
    assert Permission.INTELLIGENCE_WRITE.value in combined
    assert Permission.GOVERNANCE_DECIDE.value in combined
    assert permissions_for_roles({"unknown"}) == frozenset()


def test_governance_role_does_not_inherit_analyst_mutations() -> None:
    permissions = permissions_for_roles({"governance_reviewer"})
    assert Permission.GOVERNANCE_DECIDE.value in permissions
    assert Permission.INTELLIGENCE_WRITE.value not in permissions


def test_sensitive_authorization_requires_assurance_and_recent_authentication() -> None:
    now = datetime.now(UTC)
    aal1 = _identity(roles={"administrator"}, authenticated_at=now)
    decision = authorize(
        aal1,
        Permission.SECURITY_ADMIN,
        minimum_assurance=AssuranceLevel.PHISHING_RESISTANT,
        maximum_authentication_age_seconds=600,
        now=now,
    )
    assert (decision.allowed, decision.code) == (False, "step_up_required")

    stale = _identity(
        roles={"administrator"},
        assurance=AssuranceLevel.PHISHING_RESISTANT,
        authenticated_at=now - timedelta(minutes=11),
    )
    assert (
        authorize(
            stale,
            Permission.SECURITY_ADMIN,
            minimum_assurance=AssuranceLevel.PHISHING_RESISTANT,
            maximum_authentication_age_seconds=600,
            now=now,
        ).code
        == "recent_authentication_required"
    )


def test_identity_context_copies_mutable_attributes() -> None:
    source = {"department": "security"}
    identity = _identity(roles={"viewer"})
    immutable = IdentityContext(
        **{
            field: getattr(identity, field)
            for field in identity.__dataclass_fields__
            if field != "attributes"
        },
        attributes=source,
    )
    source["department"] = "attacker-controlled"
    assert immutable.attributes["department"] == "security"
    with pytest.raises(TypeError):
        immutable.attributes["department"] = "changed"  # type: ignore[index]


def test_service_jwt_is_audience_purpose_and_lifetime_bound() -> None:
    now = datetime.now(UTC)
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    claims = service_claims(
        workload="gateway-service",
        environment="test",
        receiver="governance-service",
        now=now,
    )
    token = sign_eddsa(
        claims, private_key, kid="gateway-2026-07", token_type="gr+s2s-jwt"  # noqa: S106
    )
    verified = verify_eddsa(
        token,
        {"gateway-2026-07": public_key},
        expected_type="gr+s2s-jwt",
        issuer=claims["iss"],
        subject=claims["sub"],
        audience=claims["aud"],
        now=now,
    )
    assert verified.claims["sub"] == claims["sub"]

    with pytest.raises(TokenValidationError, match="audience"):
        verify_eddsa(
            token,
            {"gateway-2026-07": public_key},
            expected_type="gr+s2s-jwt",
            issuer=claims["iss"],
            audience="urn:ghostrecon:test:service:reporting-service",
            now=now,
        )
    with pytest.raises(ValueError, match="lifetime"):
        service_claims(
            workload="gateway-service",
            environment="test",
            receiver="governance-service",
            lifetime_seconds=301,
        )


def test_obo_envelope_is_45_seconds_and_operation_bound() -> None:
    now = datetime.now(UTC)
    claims = obo_claims(
        gateway_principal="urn:ghostrecon:test:workload:gateway-service",
        human_subject="oidc|alice",
        audience="urn:ghostrecon:test:service:governance-service",
        operation="governance.review.approve",
        correlation_id="correlation",
        assurance="aal2_phishing_resistant",
        authentication_method="webauthn",
        authenticated_at=now,
        mapping_version="mapping.v1",
        policy_version="sprint25.v1",
        now=now,
    )
    assert claims["exp"] - claims["iat"] == 45
    assert claims["operation"] == "governance.review.approve"


def test_session_values_are_opaque_hmac_digests() -> None:
    key = b"k" * 32
    values = create_session_secrets(key)
    assert values.identifier not in values.identifier_digest
    assert values.csrf_token not in values.csrf_digest
    assert verify_secret(values.identifier, values.identifier_digest, key)
    assert not verify_secret(values.identifier + "x", values.identifier_digest, key)
    with pytest.raises(ValueError, match="256 bits"):
        create_session_secrets(b"short")


def test_oidc_transaction_uses_pkce_and_rejects_open_redirects() -> None:
    transaction = OIDCTransaction.create("/reviews?status=pending")
    assert len(transaction.state) >= 40
    assert len(transaction.nonce) >= 40
    assert transaction.code_challenge != transaction.code_verifier
    assert validate_return_path("/safe") == "/safe"
    for unsafe in ("https://attacker.example/", "//attacker.example/", "relative"):
        with pytest.raises(ValueError, match="relative"):
            validate_return_path(unsafe)


def test_oidc_metadata_and_authorization_url_are_issuer_anchored() -> None:
    metadata = OIDCProviderMetadata.parse(
        {
            "issuer": "https://login.example.test",
            "authorization_endpoint": "https://login.example.test/authorize",
            "token_endpoint": "https://login.example.test/oauth/token",
            "jwks_uri": "https://login.example.test/.well-known/jwks.json",
        },
        configured_issuer="https://login.example.test",
    )
    transaction = OIDCTransaction.create()
    url = authorization_url(
        metadata,
        transaction,
        client_id="client",
        redirect_uri="https://app.example.test/auth/callback",
    )
    assert "code_challenge_method=S256" in url
    assert f"state={transaction.state}" in url
    assert discovery_url(metadata.issuer).endswith("/.well-known/openid-configuration")
    with pytest.raises(TokenValidationError, match="issuer"):
        OIDCProviderMetadata.parse(
            {
                "issuer": "https://attacker.example",
                "authorization_endpoint": "https://attacker.example/authorize",
                "token_endpoint": "https://attacker.example/token",
                "jwks_uri": "https://attacker.example/jwks",
            },
            configured_issuer="https://login.example.test",
        )


def test_oidc_id_token_verification_is_strict() -> None:
    now = datetime.now(UTC)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "provider-key",
                "use": "sig",
                "alg": "RS256",
                "n": _b64int(public_numbers.n),
                "e": _b64int(public_numbers.e),
            }
        ]
    }
    claims = {
        "iss": "https://login.example.test",
        "sub": "oidc|alice",
        "aud": "client",
        "nonce": "nonce",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "email_verified": True,
    }
    token = _rsa_token(private_key, claims)
    verified = verify_oidc_id_token(
        token,
        jwks,
        issuer="https://login.example.test",
        audience="client",
        nonce="nonce",
        now=now,
    )
    assert verified["sub"] == "oidc|alice"
    with pytest.raises(TokenValidationError, match="nonce"):
        verify_oidc_id_token(
            token,
            jwks,
            issuer="https://login.example.test",
            audience="client",
            nonce="wrong",
            now=now,
        )
    with pytest.raises(ValueError, match="allowlist"):
        verify_oidc_id_token(
            token,
            jwks,
            issuer="https://login.example.test",
            audience="client",
            nonce="nonce",
            allowed_algorithms=frozenset({"HS256"}),
            now=now,
        )


def _b64int(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _rsa_token(private_key: rsa.RSAPrivateKey, claims: dict[str, object]) -> str:
    header = {"alg": "RS256", "kid": "provider-key", "typ": "JWT"}
    encoded_header = _json_segment(header)
    encoded_claims = _json_segment(claims)
    body = f"{encoded_header}.{encoded_claims}".encode()
    signature = private_key.sign(body, padding.PKCS1v15(), hashes.SHA256())
    return f"{body.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def _json_segment(value: dict[str, object]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
