from __future__ import annotations

from typing import Any

from ghostrecon.models.db import (
    AuditEvent,
    OutboxEvent,
)


class RepositoryEventsMixin:
    def _audit(
        self, actor: str, action: str, entity_type: str, entity_id: str, idempotency_key: str
    ) -> None:
        self.session.add(
            AuditEvent(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                idempotency_key=idempotency_key,
                payload={},
            )
        )

    def _enqueue_event(self, event: Any) -> OutboxEvent:
        payload = event.model_dump(mode="json")
        outbox_event = OutboxEvent(
            event_name=payload["event_name"],
            aggregate_type=payload["aggregate_type"],
            aggregate_id=payload["aggregate_id"],
            idempotency_key=payload["idempotency_key"],
            payload=payload,
        )
        self.session.add(outbox_event)
        return outbox_event
