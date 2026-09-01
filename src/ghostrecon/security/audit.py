from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from ghostrecon.common.config import get_settings
from ghostrecon.models.db.governance import AuditEvent

from .context import current_identity, current_operation

_REDACTED = "[redacted]"
_SENSITIVE = frozenset(
    {
        "authorization",
        "cookie",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "password",
        "secret",
        "otp",
        "code",
        "email_body",
        "provider_payload",
        "private_key",
    }
)


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _REDACTED if str(key).lower() in _SENSITIVE else redact(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [redact(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)[:256]


def integrity_hmac(event_record: AuditEvent, key: bytes) -> str:
    payload = {
        "actor": event_record.actor,
        "action": event_record.action,
        "operation": event_record.operation,
        "permission": event_record.permission,
        "decision": event_record.decision,
        "entity_type": event_record.entity_type,
        "entity_id": event_record.entity_id,
        "correlation_id": event_record.correlation_id,
        "payload": redact(event_record.payload),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hmac.new(key, canonical.encode(), hashlib.sha256).hexdigest()


@event.listens_for(Session, "before_flush")
def secure_audit_events(session: Session, *_: object) -> None:
    settings = get_settings()
    identity = current_identity.get()
    operation = current_operation.get()
    for record in session.new:
        if not isinstance(record, AuditEvent):
            continue
        if settings.strict_runtime and (
            identity is None or operation is None or not settings.audit_hmac_key
        ):
            raise RuntimeError("verified audit context is unavailable")
        record.payload = redact(record.payload)
        record.network_metadata = redact(record.network_metadata)
        if identity is not None:
            record.actor = identity.actor_label
            record.human_subject = (
                identity.represented_subject if identity.identity_type.value == "human" else None
            )
            record.service_subject = identity.calling_service
            record.on_behalf_of_subject = identity.on_behalf_of_subject
            record.identity_type = identity.identity_type.value
            record.operation = operation
            record.assurance = identity.assurance.value
            record.policy_version = identity.permission_policy_version
            record.mapping_version = identity.claim_mapping_version
            record.environment = identity.environment
            record.request_id = identity.request_id
            record.correlation_id = identity.correlation_id
        record.decision = record.decision or "allowed"
        if settings.audit_hmac_key:
            record.integrity_hmac = integrity_hmac(record, settings.audit_hmac_key.encode())
