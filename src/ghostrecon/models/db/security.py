from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ghostrecon.common.database import Base

from .common import utcnow


class SecurityPrincipal(Base):
    __tablename__ = "security_principals"
    __table_args__ = (UniqueConstraint("issuer", "subject", name="uq_security_principal"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_label: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role_ceiling: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    mapping_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SecurityRoleBinding(Base):
    __tablename__ = "security_role_bindings"
    __table_args__ = (
        UniqueConstraint("principal_id", "role", name="uq_security_role_binding"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    principal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("security_principals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    granted_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecuritySession(Base):
    __tablename__ = "security_sessions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    principal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("security_principals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    identifier_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authentication_method: Mapped[str] = mapped_column(String(128), nullable=False)
    assurance: Mapped[str] = mapped_column(String(64), nullable=False)
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_roles_refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotate_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    remembered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(255))
    mapping_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecurityEmergencyGrant(Base):
    __tablename__ = "security_emergency_grants"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    principal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("security_principals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permissions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    approver_evidence: Mapped[str] = mapped_column(String(512), nullable=False)
    assurance: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecurityReplayMarker(Base):
    __tablename__ = "security_replay_markers"

    namespace: Mapped[str] = mapped_column(String(64), primary_key=True)
    jti_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecurityPolicyVersion(Base):
    __tablename__ = "security_policy_versions"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
