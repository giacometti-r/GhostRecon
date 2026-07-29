from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.events.contracts import EventName, new_event
from ghostrecon.models.api import (
    SuppressionCheckRequest,
    SuppressionCheckResult,
    SuppressionCreate,
    SuppressionOut,
)
from ghostrecon.models.db import (
    Suppression,
)


def evaluate_suppression(request: SuppressionCheckRequest) -> SuppressionCheckResult:
    """Evaluate non-database suppression rules that must always apply."""

    if request.email:
        local_part = str(request.email).split("@", 1)[0].lower()
        if local_part in ROLE_BASED_PREFIXES:
            return SuppressionCheckResult(
                allowed=False,
                reason="Role-based address requires explicit approval before outreach",
            )

    if request.channel.lower() not in SUPPORTED_CHANNELS:
        return SuppressionCheckResult(allowed=False, reason="Unsupported outreach channel")

    return SuppressionCheckResult(allowed=True)


async def evaluate_suppression_with_store(
    request: SuppressionCheckRequest,
    *,
    settings: Settings | None = None,
) -> SuppressionCheckResult:
    baseline = evaluate_suppression(request)
    if not baseline.allowed:
        return baseline

    matches = []
    if request.email:
        matches.append(Suppression.email == str(request.email).lower())
    if request.domain:
        matches.append(Suppression.domain == request.domain.lower())
    if request.contact_id:
        matches.append(Suppression.contact_id == request.contact_id)
    if not matches:
        return baseline

    async with session_scope(settings) as session:
        suppression = await session.scalar(
            select(Suppression)
            .where(Suppression.active.is_(True))
            .where(Suppression.channel == request.channel.lower())
            .where(
                or_(
                    Suppression.expires_at.is_(None),
                    Suppression.expires_at > datetime.now(UTC),
                )
            )
            .where(or_(*matches))
            .limit(1)
        )
        if suppression is None:
            return baseline
        return SuppressionCheckResult(allowed=False, reason=suppression.reason)


async def create_suppression(
    request: SuppressionCreate,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> Suppression:
    async with session_scope(settings) as session:
        existing = await session.scalar(
            select(Suppression).where(Suppression.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing

        suppression = Suppression(
            email=str(request.email).lower() if request.email else None,
            domain=request.domain.lower() if request.domain else None,
            contact_id=request.contact_id,
            channel=request.channel.lower(),
            target_type=request.target_type,
            target_id=request.target_id,
            reason=request.reason,
            source=request.source,
            active=request.active,
            expires_at=request.expires_at,
            policy_snapshot=dict(request.policy_snapshot),
            idempotency_key=idempotency_key,
        )
        session.add(suppression)
        await session.flush()
        _audit(
            session,
            actor,
            "suppression.created",
            "suppression",
            suppression.id,
            idempotency_key=f"audit:{idempotency_key}",
            payload=suppression_to_api(suppression),
        )
        _enqueue_event(
            session,
            new_event(
                event_name=EventName.SUPPRESSION_CREATED,
                aggregate_type="suppression",
                aggregate_id=suppression.id,
                source_service="governance-service",
                payload=suppression_to_api(suppression),
                idempotency_key=f"suppression.created:{suppression.id}",
            ),
        )
        return suppression


def suppression_to_api(suppression: Suppression) -> dict[str, object]:
    return {
        "id": suppression.id,
        "email": suppression.email,
        "domain": suppression.domain,
        "contact_id": suppression.contact_id,
        "channel": suppression.channel,
        "target_type": suppression.target_type,
        "target_id": suppression.target_id,
        "reason": suppression.reason,
        "source": suppression.source,
        "active": suppression.active,
        "expires_at": suppression.expires_at,
        "policy_snapshot": suppression.policy_snapshot or {},
        "created_at": suppression.created_at,
    }


def suppression_to_model(suppression: Suppression) -> SuppressionOut:
    return SuppressionOut.model_validate(suppression_to_api(suppression))


from .policy import ROLE_BASED_PREFIXES, SUPPORTED_CHANNELS  # noqa: E402  # noqa: E402
from .review_records import _audit, _enqueue_event  # noqa: E402
