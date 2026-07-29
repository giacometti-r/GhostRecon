from __future__ import annotations

from sqlalchemy import select

from ghostrecon.common.config import Settings, get_settings
from ghostrecon.common.configuration import assert_adapter_allowed
from ghostrecon.common.database import session_scope
from ghostrecon.models.api import (
    SequenceEmailAlertCreate,
    SequenceEmailAlertOut,
)
from ghostrecon.models.db import (
    SequenceEmailAlert,
    SequenceEnrollment,
)
from ghostrecon.services.sequence_adapters import (
    SmtpSender,
    SmtpSendRequest,
    StdlibSmtpSender,
)


async def create_sequence_email_alert(
    enrollment_id: str,
    request: SequenceEmailAlertCreate,
    *,
    actor: str,
    idempotency_key: str,
    settings: Settings | None = None,
) -> SequenceEmailAlertOut | None:
    async with session_scope(settings) as session:
        enrollment = await session.get(SequenceEnrollment, enrollment_id)
        if enrollment is None:
            return None
        existing = await session.scalar(
            select(SequenceEmailAlert).where(SequenceEmailAlert.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return sequence_email_alert_to_model(existing)
        alert = SequenceEmailAlert(
            enrollment_id=enrollment.id,
            recipient_email=str(request.recipient_email).lower(),
            subject=request.subject,
            body=request.body,
            send_at=request.send_at or utcnow(),
            status="pending",
            actor=actor,
            idempotency_key=idempotency_key,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(alert)
        await session.flush()
        return sequence_email_alert_to_model(alert)


async def process_due_sequence_email_alerts(
    *,
    limit: int = 50,
    settings: Settings | None = None,
    sender: SmtpSender | None = None,
) -> dict[str, object]:
    resolved = settings or get_settings()
    smtp_sender = sender or StdlibSmtpSender(resolved)
    assert_adapter_allowed(resolved, smtp_sender, "smtp_provider")
    now = utcnow()
    async with session_scope(resolved) as session:
        result = await session.execute(
            select(SequenceEmailAlert)
            .where(SequenceEmailAlert.status == "pending")
            .where(SequenceEmailAlert.send_at <= now)
            .order_by(SequenceEmailAlert.send_at.asc(), SequenceEmailAlert.id.asc())
            .limit(limit)
        )
        alerts = list(result.scalars())
        outcomes: list[dict[str, object]] = []
        for alert in alerts:
            message_id = f"<ghostrecon-alert-{alert.id}@local>"
            try:
                sent = smtp_sender.send(
                    SmtpSendRequest(
                        from_email=resolved.smtp_from_address.lower(),
                        to_email=alert.recipient_email,
                        subject=alert.subject,
                        body=alert.body,
                        message_id=message_id,
                    )
                )
            except Exception as exc:
                alert.status = "failed_retryable"
                alert.last_error = str(exc)
                alert.updated_at = utcnow()
                outcomes.append({"alert_id": alert.id, "status": alert.status, "reason": str(exc)})
                continue
            alert.status = "sent"
            alert.provider_message_id = sent.provider_message_id
            alert.sent_at = utcnow()
            alert.updated_at = utcnow()
            outcomes.append({"alert_id": alert.id, "status": alert.status})
        return {"processed": len(outcomes), "outcomes": outcomes}


from .common import utcnow  # noqa: E402
from .serializers import sequence_email_alert_to_model  # noqa: E402
