from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ghostrecon.common.config import Settings

from .identity import AssuranceLevel, IdentityContext, IdentityType
from .jwt import (
    TokenValidationError,
    obo_claims,
    service_claims,
    sign_eddsa,
    verify_eddsa,
)
from .policy import permissions_for_roles
from .transactions import RedisReplayDetector

SERVICE_HEADER = "X-GhostRecon-Service-Authorization"
OBO_HEADER = "X-GhostRecon-OBO"
SERVICE_JWT_PURPOSE = "ghostrecon-service+jwt"
OBO_JWT_PURPOSE = "ghostrecon-obo+jwt"


@dataclass(frozen=True, slots=True)
class TrustedWorkload:
    issuer: str
    public_keys: Mapping[str, Ed25519PublicKey]


class FileCredentialProvider:
    """Load immutable Ed25519 credentials from read-only deployment files."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def private_key(self) -> Ed25519PrivateKey:
        if not self.settings.service_private_key_path:
            raise RuntimeError("service private key path is not configured")
        value = Path(self.settings.service_private_key_path).read_bytes()
        key = serialization.load_pem_private_key(value, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise RuntimeError("service private key must be Ed25519")
        return key

    def trust_bundle(self) -> dict[str, TrustedWorkload]:
        if not self.settings.service_trust_bundle_path:
            raise RuntimeError("service trust bundle path is not configured")
        raw = json.loads(Path(self.settings.service_trust_bundle_path).read_text())
        workloads = raw.get("workloads")
        if not isinstance(workloads, dict):
            raise RuntimeError("invalid service trust bundle")
        result: dict[str, TrustedWorkload] = {}
        for name, record in workloads.items():
            if not isinstance(name, str) or not isinstance(record, dict):
                raise RuntimeError("invalid service trust bundle")
            issuer, raw_keys = record.get("issuer"), record.get("keys")
            if not isinstance(issuer, str) or not isinstance(raw_keys, dict):
                raise RuntimeError("invalid service trust bundle")
            keys: dict[str, Ed25519PublicKey] = {}
            for kid, encoded in raw_keys.items():
                if not isinstance(kid, str) or not isinstance(encoded, str):
                    raise RuntimeError("invalid service trust bundle")
                try:
                    key_bytes = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
                    keys[kid] = Ed25519PublicKey.from_public_bytes(key_bytes)
                except (ValueError, TypeError) as exc:
                    raise RuntimeError("invalid service trust bundle") from exc
            result[name] = TrustedWorkload(issuer, keys)
        return result


class WorkloadSigner:
    def __init__(self, settings: Settings, provider: FileCredentialProvider | None = None) -> None:
        self.settings = settings
        self.provider = provider or FileCredentialProvider(settings)

    def service_token(self, receiver: str) -> str:
        identity = self._identity()
        claims = service_claims(
            workload=identity,
            environment=self.settings.profile.value,
            receiver=receiver,
            lifetime_seconds=self.settings.service_token_lifetime_seconds,
        )
        return sign_eddsa(
            claims,
            self.provider.private_key(),
            kid=self._kid(),
            token_type=SERVICE_JWT_PURPOSE,
        )

    def obo_token(self, identity: IdentityContext, policy_owner: str, operation: str) -> str:
        principal = f"urn:ghostrecon:{self.settings.profile.value}:workload:{self._identity()}"
        claims = obo_claims(
            gateway_principal=principal,
            human_subject=identity.represented_subject,
            audience=f"urn:ghostrecon:{self.settings.profile.value}:service:{policy_owner}",
            operation=operation,
            correlation_id=identity.correlation_id,
            assurance=identity.assurance.value,
            authentication_method=identity.authentication_method,
            authenticated_at=identity.authenticated_at,
            mapping_version=identity.claim_mapping_version,
            policy_version=identity.permission_policy_version,
        )
        claims["roles"] = sorted(identity.roles)
        claims["permissions"] = sorted(identity.permissions)
        return sign_eddsa(
            claims,
            self.provider.private_key(),
            kid=self._kid(),
            token_type=OBO_JWT_PURPOSE,
        )

    def _identity(self) -> str:
        if not self.settings.service_identity:
            raise RuntimeError("service identity is not configured")
        return self.settings.service_identity

    def _kid(self) -> str:
        if not self.settings.service_private_key_id:
            raise RuntimeError("service private key id is not configured")
        return self.settings.service_private_key_id


class WorkloadVerifier:
    def __init__(
        self,
        settings: Settings,
        provider: FileCredentialProvider | None = None,
        replay_detector: RedisReplayDetector | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider or FileCredentialProvider(settings)
        self.replay_detector = replay_detector

    async def resolve(self, request: Any) -> IdentityContext | None:
        service_token = request.headers.get(SERVICE_HEADER)
        obo_token = request.headers.get(OBO_HEADER)
        if not service_token:
            return None
        bundle = self.provider.trust_bundle()
        verified_service, caller = self._verify_service(service_token, bundle)
        if not obo_token:
            return self._service_identity(verified_service.claims, caller, request)
        trusted = bundle[caller]
        audience = (
            f"urn:ghostrecon:{self.settings.profile.value}:service:"
            f"{self.settings.service_name.value}"
        )
        obo = verify_eddsa(
            obo_token,
            trusted.public_keys,
            expected_type=OBO_JWT_PURPOSE,
            issuer=trusted.issuer,
            audience=audience,
            maximum_lifetime_seconds=45,
        )
        claims = obo.claims
        if self.replay_detector is not None:
            accepted = await self.replay_detector.consume(
                purpose="obo",
                jti=str(claims.get("jti", "")),
                expires_in_seconds=max(1, int(claims["exp"]) - int(datetime.now(UTC).timestamp())),
            )
            if not accepted:
                raise TokenValidationError("replayed represented identity")
        return IdentityContext(
            identity_type=IdentityType.HUMAN,
            subject=str(claims["sub"]),
            actor_label=str(claims["sub"]),
            issuer=str(claims["iss"]),
            audience=(audience,),
            roles=frozenset(_string_list(claims.get("roles"))),
            permissions=frozenset(_string_list(claims.get("permissions"))),
            calling_service=caller,
            on_behalf_of_subject=str(claims["sub"]),
            authentication_method=str(claims["authentication_method"]),
            authenticated_at=datetime.fromtimestamp(int(claims["authenticated_at"]), UTC),
            assurance=AssuranceLevel(str(claims["assurance"])),
            session_id=None,
            correlation_id=str(claims["correlation_id"]),
            request_id=request.state.correlation_id,
            claim_mapping_version=str(claims["mapping_version"]),
            permission_policy_version=str(claims["policy_version"]),
            environment=self.settings.profile.value,
            attributes={"obo_operation": str(claims["operation"])},
        )

    def _verify_service(self, token: str, bundle: Mapping[str, TrustedWorkload]) -> tuple[Any, str]:
        for caller, trusted in bundle.items():
            try:
                audience = (
                    f"urn:ghostrecon:{self.settings.profile.value}:service:"
                    f"{self.settings.service_name.value}"
                )
                return (
                    verify_eddsa(
                        token,
                        trusted.public_keys,
                        expected_type=SERVICE_JWT_PURPOSE,
                        issuer=trusted.issuer,
                        audience=audience,
                        maximum_lifetime_seconds=300,
                    ),
                    caller,
                )
            except TokenValidationError:
                continue
        raise TokenValidationError("untrusted workload")

    def _service_identity(
        self, claims: Mapping[str, Any], caller: str, request: Any
    ) -> IdentityContext:
        issued_at = datetime.fromtimestamp(int(claims["iat"]), UTC)
        return IdentityContext(
            identity_type=IdentityType.SERVICE,
            subject=str(claims["sub"]),
            actor_label=caller,
            issuer=str(claims["iss"]),
            audience=(str(claims["aud"]),),
            roles=frozenset(),
            permissions=permissions_for_roles(set()),
            calling_service=caller,
            on_behalf_of_subject=None,
            authentication_method="eddsa_workload_jwt",
            authenticated_at=issued_at,
            assurance=AssuranceLevel.WORKLOAD,
            session_id=None,
            correlation_id=request.state.correlation_id,
            request_id=request.state.correlation_id,
            claim_mapping_version="workload.v1",
            permission_policy_version="sprint25b.v1",
            environment=self.settings.profile.value,
        )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TokenValidationError("invalid represented identity")
    return value
