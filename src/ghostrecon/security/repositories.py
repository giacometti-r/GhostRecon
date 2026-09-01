from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ghostrecon.common.config import Settings
from ghostrecon.models.db.governance import AuditEvent
from ghostrecon.models.db.security import (
    SecurityPrincipal,
    SecurityRoleBinding,
    SecuritySession,
)

from .identity import AssuranceLevel, IdentityContext, IdentityType
from .policy import POLICY_VERSION, permissions_for_roles
from .sessions import (
    SessionSecrets,
    create_session_secrets,
    csrf_token_for_session,
    digest_secret,
    verify_secret,
)


@dataclass(frozen=True, slots=True)
class CreatedSession:
    record_id: str
    secrets: SessionSecrets
    idle_expires_at: datetime
    absolute_expires_at: datetime


class SecurityRepository:
    """PostgreSQL-authoritative principal and revocable session storage."""

    def __init__(self, factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self.factory = factory
        self.settings = settings
        if not settings.session_hmac_key:
            raise ValueError("session HMAC key is required")
        self.hmac_key = settings.session_hmac_key.encode()

    async def provision_from_claims(
        self,
        claims: dict[str, object],
        *,
        provider_roles: frozenset[str],
        allow_create: bool = False,
    ) -> SecurityPrincipal:
        issuer, subject = str(claims["iss"]), str(claims["sub"])
        async with self.factory.begin() as session:
            await self._install_security_context(session)
            principal = await session.scalar(
                select(SecurityPrincipal).where(
                    SecurityPrincipal.issuer == issuer,
                    SecurityPrincipal.subject == subject,
                )
            )
            if principal is None:
                if not allow_create:
                    raise PermissionError("principal is not provisioned")
                principal = SecurityPrincipal(
                    issuer=issuer,
                    subject=subject,
                    actor_label=str(claims.get("email") or subject)[:255],
                    email=str(claims.get("email"))[:320] if claims.get("email") else None,
                    email_verified=claims.get("email_verified") is True,
                    disabled=False,
                    role_ceiling=sorted(provider_roles),
                    mapping_version="oidc.v1",
                    policy_version=POLICY_VERSION,
                )
                session.add(principal)
                await session.flush()
                for role in sorted(provider_roles):
                    session.add(
                        SecurityRoleBinding(
                            principal_id=principal.id,
                            role=role,
                            granted_by_subject=subject,
                            reason="initial deterministic local provisioning",
                        )
                    )
            if principal.disabled:
                raise PermissionError("principal is disabled")
            return principal

    async def create_session(
        self,
        principal: SecurityPrincipal,
        *,
        authentication_method: str,
        assurance: AssuranceLevel,
        provider_roles: frozenset[str],
        remembered: bool,
        authenticated_at: datetime,
    ) -> CreatedSession:
        now = datetime.now(UTC)
        idle = (
            self.settings.remembered_session_idle_seconds
            if remembered
            else self.settings.session_idle_seconds
        )
        absolute = (
            self.settings.remembered_session_absolute_seconds
            if remembered
            else self.settings.session_absolute_seconds
        )
        secrets = create_session_secrets(self.hmac_key)
        csrf_token = csrf_token_for_session(secrets.identifier, self.hmac_key)
        secrets = SessionSecrets(
            secrets.identifier,
            secrets.identifier_digest,
            csrf_token,
            digest_secret(csrf_token, self.hmac_key),
        )
        record = SecuritySession(
            principal_id=principal.id,
            identifier_digest=secrets.identifier_digest,
            csrf_digest=secrets.csrf_digest,
            authentication_method=authentication_method,
            assurance=assurance.value,
            authenticated_at=authenticated_at,
            provider_roles_refreshed_at=now,
            provider_roles=sorted(provider_roles),
            last_seen_at=now,
            rotate_after=now + timedelta(seconds=self.settings.session_rotation_seconds),
            idle_expires_at=now + timedelta(seconds=idle),
            absolute_expires_at=now + timedelta(seconds=absolute),
            remembered=remembered,
            mapping_version=principal.mapping_version,
            policy_version=principal.policy_version,
        )
        async with self.factory.begin() as session:
            await self._install_security_context(session)
            session.add(record)
        return CreatedSession(
            record.id, secrets, record.idle_expires_at, record.absolute_expires_at
        )

    async def resolve(self, raw_identifier: str, *, correlation_id: str) -> IdentityContext | None:
        now = datetime.now(UTC)
        digest = digest_secret(raw_identifier, self.hmac_key)
        async with self.factory.begin() as session:
            await self._install_security_context(session)
            result = await session.execute(
                select(SecuritySession, SecurityPrincipal)
                .join(SecurityPrincipal, SecurityPrincipal.id == SecuritySession.principal_id)
                .where(SecuritySession.identifier_digest == digest)
                .with_for_update(of=SecuritySession)
            )
            row = result.one_or_none()
            if row is None:
                return None
            record, principal = row
            if (
                record.revoked_at is not None
                or principal.disabled
                or record.idle_expires_at <= now
                or record.absolute_expires_at <= now
                or record.mapping_version != principal.mapping_version
                or record.policy_version != principal.policy_version
            ):
                if record.revoked_at is None:
                    record.revoked_at = now
                    record.revocation_reason = "expired_or_invalidated"
                return None
            bindings = (
                await session.scalars(
                    select(SecurityRoleBinding).where(
                        SecurityRoleBinding.principal_id == principal.id,
                        (
                            SecurityRoleBinding.expires_at.is_(None)
                            | (SecurityRoleBinding.expires_at > now)
                        ),
                    )
                )
            ).all()
            locally_granted = {binding.role for binding in bindings}
            roles = locally_granted & set(record.provider_roles) & set(principal.role_ceiling)
            record.last_seen_at = now
            idle_seconds = (
                self.settings.remembered_session_idle_seconds
                if record.remembered
                else self.settings.session_idle_seconds
            )
            record.idle_expires_at = min(
                now + timedelta(seconds=idle_seconds), record.absolute_expires_at
            )
            return IdentityContext(
                identity_type=IdentityType.HUMAN,
                subject=principal.subject,
                actor_label=principal.actor_label,
                issuer=principal.issuer,
                audience=(self.settings.oidc_client_id or "ghostrecon-gateway",),
                roles=frozenset(roles),
                permissions=permissions_for_roles(roles),
                calling_service=None,
                on_behalf_of_subject=None,
                authentication_method=record.authentication_method,
                authenticated_at=record.authenticated_at,
                assurance=AssuranceLevel(record.assurance),
                session_id=UUID(record.id),
                correlation_id=correlation_id,
                request_id=correlation_id,
                claim_mapping_version=record.mapping_version,
                permission_policy_version=record.policy_version,
                environment=self.settings.profile.value,
                email_verified=principal.email_verified,
                attributes={
                    "csrf_digest": record.csrf_digest,
                    "idle_expires_at": record.idle_expires_at.isoformat(),
                    "absolute_expires_at": record.absolute_expires_at.isoformat(),
                    "provider_roles_refreshed_at": record.provider_roles_refreshed_at.isoformat(),
                },
            )

    async def revoke(self, session_id: str, *, reason: str) -> bool:
        async with self.factory.begin() as session:
            await self._install_security_context(session)
            result = await session.execute(
                update(SecuritySession)
                .where(SecuritySession.id == session_id, SecuritySession.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC), revocation_reason=reason[:255])
            )
            return bool(result.rowcount)

    async def revoke_subject(self, subject: str, *, reason: str) -> int:
        async with self.factory.begin() as session:
            await self._install_security_context(session)
            result = await session.execute(
                update(SecuritySession)
                .where(
                    and_(
                        SecuritySession.principal_id.in_(
                            select(SecurityPrincipal.id).where(SecurityPrincipal.subject == subject)
                        ),
                        SecuritySession.revoked_at.is_(None),
                    )
                )
                .values(revoked_at=datetime.now(UTC), revocation_reason=reason[:255])
            )
            return int(result.rowcount or 0)

    async def list_principals(self, *, limit: int = 100) -> list[SecurityPrincipal]:
        async with self.factory.begin() as session:
            await self._install_security_context(session)
            return list(
                (
                    await session.scalars(
                        select(SecurityPrincipal)
                        .order_by(SecurityPrincipal.created_at.desc())
                        .limit(min(limit, 200))
                    )
                ).all()
            )

    async def get_principal(self, principal_id: str) -> SecurityPrincipal | None:
        async with self.factory.begin() as session:
            await self._install_security_context(session)
            return await session.get(SecurityPrincipal, principal_id)

    async def update_principal(
        self,
        principal_id: str,
        *,
        disabled: bool,
        roles: frozenset[str],
        expected_mapping_version: str,
        actor_subject: str,
        reason: str,
    ) -> SecurityPrincipal | None:
        async with self.factory.begin() as session:
            await self._install_security_context(session)
            principal = await session.get(SecurityPrincipal, principal_id, with_for_update=True)
            if principal is None:
                return None
            if principal.mapping_version != expected_mapping_version:
                raise RuntimeError("principal version conflict")
            principal.disabled = disabled
            principal.role_ceiling = sorted(roles)
            principal.mapping_version = f"admin-{uuid4().hex}"
            await session.execute(
                delete(SecurityRoleBinding).where(SecurityRoleBinding.principal_id == principal_id)
            )
            for role in sorted(roles):
                session.add(
                    SecurityRoleBinding(
                        principal_id=principal_id,
                        role=role,
                        granted_by_subject=actor_subject,
                        reason=reason[:512],
                    )
                )
            await session.execute(
                update(SecuritySession)
                .where(
                    SecuritySession.principal_id == principal_id,
                    SecuritySession.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(UTC), revocation_reason="principal_changed")
            )
            return principal

    async def principal_sessions(self, principal_id: str) -> list[SecuritySession]:
        async with self.factory.begin() as session:
            await self._install_security_context(session)
            return list(
                (
                    await session.scalars(
                        select(SecuritySession)
                        .where(SecuritySession.principal_id == principal_id)
                        .order_by(SecuritySession.created_at.desc())
                        .limit(100)
                    )
                ).all()
            )

    async def revoke_principal_sessions(self, principal_id: str, *, reason: str) -> int:
        async with self.factory.begin() as session:
            await self._install_security_context(session)
            result = await session.execute(
                update(SecuritySession)
                .where(
                    SecuritySession.principal_id == principal_id,
                    SecuritySession.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(UTC), revocation_reason=reason[:255])
            )
            return int(result.rowcount or 0)

    async def audit_events(self, *, limit: int = 100) -> list[AuditEvent]:
        async with self.factory.begin() as session:
            await self._install_security_context(session)
            return list(
                (
                    await session.scalars(
                        select(AuditEvent)
                        .order_by(AuditEvent.created_at.desc())
                        .limit(min(limit, 200))
                    )
                ).all()
            )

    async def _install_security_context(self, session: AsyncSession) -> None:
        """Install the gateway security-store context before forced-RLS access."""
        values = {
            "ghostrecon.context_valid": "1",
            "ghostrecon.calling_workload": self.settings.service_identity or "gateway-service",
            "ghostrecon.permissions": "security.admin,session.manage",
        }
        for key, value in values.items():
            await session.execute(
                text("SELECT set_config(:key, :value, true)"), {"key": key, "value": value}
            )

    def verify_csrf(self, token: str | None, identity: IdentityContext) -> bool:
        expected = identity.attributes.get("csrf_digest")
        return isinstance(expected, str) and verify_secret(token, expected, self.hmac_key)
