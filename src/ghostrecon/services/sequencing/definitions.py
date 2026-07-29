from __future__ import annotations

from sqlalchemy import select

from ghostrecon.common.config import Settings
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    SequenceCreateRequest,
    SequenceList,
    SequenceOut,
    SequenceUpdateRequest,
)
from ghostrecon.models.db import (
    Sequence,
    SequenceStep,
)


async def create_sequence(
    request: SequenceCreateRequest,
    *,
    actor: str,
    idempotency_key: str | None = None,
    settings: Settings | None = None,
) -> SequenceOut:
    _ = actor
    async with session_scope(settings) as session:
        if idempotency_key:
            existing = await session.scalar(
                select(Sequence).where(Sequence.idempotency_key == idempotency_key)
            )
            if existing is not None:
                return sequence_to_model(existing, await _sequence_steps(session, existing.id))

        now = utcnow()
        sequence = Sequence(
            name=request.name,
            owner_id=request.owner_id,
            channel=request.channel.value,
            status="active",
            rate_limit_policy=dict(request.rate_limit_policy),
            definition_version=1,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        session.add(sequence)
        await session.flush()
        steps: list[SequenceStep] = []
        for index, step_request in enumerate(request.steps, start=1):
            step = SequenceStep(
                sequence_id=sequence.id,
                step_order=step_request.step_order or index,
                channel=step_request.channel.value,
                delay_seconds=step_request.delay_seconds,
                subject_template=step_request.subject_template,
                body_template=step_request.body_template,
                requires_approval=_requires_approval(
                    step_request.channel.value,
                    step_request.requires_approval,
                ),
                step_metadata=dict(step_request.step_metadata),
                definition_version=sequence.definition_version,
                active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(step)
            steps.append(step)
        await session.flush()
        return sequence_to_model(sequence, sorted(steps, key=lambda item: item.step_order))


async def list_sequences(
    *,
    status: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> SequenceList:
    async with session_scope(settings) as session:
        query = select(Sequence).order_by(Sequence.created_at.desc()).limit(limit)
        if status:
            query = query.where(_fuzzy(Sequence.status, status))
        result = await session.execute(query)
        sequences = [
            sequence_to_model(sequence, await _sequence_steps(session, sequence.id))
            for sequence in result.scalars()
        ]
        return SequenceList(sequences=sequences)


async def get_sequence(
    sequence_id: str,
    *,
    settings: Settings | None = None,
) -> SequenceOut | None:
    async with session_scope(settings) as session:
        sequence = await session.get(Sequence, sequence_id)
        if sequence is None:
            return None
        return sequence_to_model(sequence, await _sequence_steps(session, sequence.id))


async def archive_sequence(
    sequence_id: str,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceOut | None:
    _ = actor
    async with session_scope(settings) as session:
        sequence = await session.get(Sequence, sequence_id)
        if sequence is None:
            return None
        sequence.status = "archived"
        sequence.updated_at = utcnow()
        return sequence_to_model(sequence, await _sequence_steps(session, sequence.id))


async def update_sequence(
    sequence_id: str,
    request: SequenceUpdateRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SequenceOut | None:
    _ = actor
    async with session_scope(settings) as session:
        sequence = await session.get(Sequence, sequence_id)
        if sequence is None:
            return None
        now = utcnow()
        if request.name is not None:
            sequence.name = request.name
        if request.owner_id is not None:
            sequence.owner_id = request.owner_id
        if request.channel is not None:
            sequence.channel = request.channel.value
        if request.status is not None:
            sequence.status = request.status.value
        if request.rate_limit_policy is not None:
            sequence.rate_limit_policy = dict(request.rate_limit_policy)
        if request.steps is not None:
            if (
                request.expected_version is not None
                and request.expected_version != sequence.definition_version
            ):
                raise ValueError("sequence definition version conflict")
            sequence.definition_version += 1
            for index, step_request in enumerate(request.steps, start=1):
                order = step_request.step_order or index
                session.add(
                    SequenceStep(
                        sequence_id=sequence.id,
                        step_order=order,
                        channel=step_request.channel.value,
                        delay_seconds=step_request.delay_seconds,
                        subject_template=step_request.subject_template,
                        body_template=step_request.body_template,
                        requires_approval=_requires_approval(
                            step_request.channel.value,
                            step_request.requires_approval,
                        ),
                        step_metadata=dict(step_request.step_metadata),
                        definition_version=sequence.definition_version,
                        active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
        sequence.updated_at = now
        await session.flush()
        return sequence_to_model(sequence, await _sequence_steps(session, sequence.id))


from .common import utcnow  # noqa: E402
from .eligibility import _fuzzy  # noqa: E402
from .queries import _requires_approval, _sequence_steps  # noqa: E402
from .serializers import sequence_to_model  # noqa: E402
