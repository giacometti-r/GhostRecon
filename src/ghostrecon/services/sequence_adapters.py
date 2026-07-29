from __future__ import annotations

import imaplib
import smtplib
from dataclasses import dataclass
from email import message_from_bytes
from email.message import EmailMessage
from typing import Protocol
from uuid import uuid4

from ghostrecon.common.config import Settings
from ghostrecon.models.api import InboundEmailEventCreate, InboundEmailEventType


@dataclass(frozen=True)
class SmtpSendRequest:
    from_email: str
    to_email: str
    subject: str
    body: str
    message_id: str


@dataclass(frozen=True)
class SmtpSendResult:
    provider_message_id: str


class SmtpSender(Protocol):
    def send(self, request: SmtpSendRequest) -> SmtpSendResult: ...


class ImapPoller(Protocol):
    def poll(self, limit: int = 50) -> list[InboundEmailEventCreate]: ...


class StdlibSmtpSender:
    def __init__(self, settings: Settings) -> None:
        if not settings.smtp_host:
            raise ValueError("GHOSTRECON_SMTP_HOST is required for SMTP sends")
        self.settings = settings

    def send(self, request: SmtpSendRequest) -> SmtpSendResult:
        message = EmailMessage()
        message["From"] = request.from_email
        message["To"] = request.to_email
        message["Subject"] = request.subject
        message["Message-ID"] = request.message_id
        message.set_content(request.body)

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            if self.settings.smtp_username:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password or "")
            smtp.send_message(message)
        return SmtpSendResult(provider_message_id=request.message_id)


class StdlibImapPoller:
    def __init__(self, settings: Settings) -> None:
        if not settings.imap_host:
            raise ValueError("GHOSTRECON_IMAP_HOST is required for IMAP polling")
        self.settings = settings

    def poll(self, limit: int = 50) -> list[InboundEmailEventCreate]:
        events: list[InboundEmailEventCreate] = []
        with imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port) as imap:
            imap.login(self.settings.imap_username or "", self.settings.imap_password or "")
            imap.select(self.settings.imap_mailbox)
            status, data = imap.search(None, "UNSEEN")
            if status != "OK" or not data:
                return events
            ids = data[0].split()[:limit]
            for msg_id in ids:
                fetch_status, fetch_data = imap.fetch(msg_id, "(RFC822)")
                if fetch_status != "OK" or not fetch_data:
                    continue
                raw = next(
                    (item[1] for item in fetch_data if isinstance(item, tuple) and item[1]),
                    None,
                )
                if raw is None:
                    continue
                message = message_from_bytes(raw)
                from_email = _extract_address(message.get("From"))
                to_email = _extract_address(message.get("To"))
                subject = str(message.get("Subject") or "")
                event_type = _classify_inbound(subject, from_email)
                events.append(
                    InboundEmailEventCreate(
                        event_type=event_type,
                        from_email=from_email,
                        to_email=to_email,
                        message_id=str(message.get("Message-ID") or uuid4()),
                        provider_payload={"subject": subject},
                    )
                )
        return events


def _classify_inbound(subject: str, from_email: str | None) -> InboundEmailEventType:
    normalized = subject.lower()
    sender = (from_email or "").lower()
    if "unsubscribe" in normalized:
        return InboundEmailEventType.UNSUBSCRIBE
    if "undeliver" in normalized or "delivery status" in normalized or "mailer-daemon" in sender:
        return InboundEmailEventType.BOUNCE
    return InboundEmailEventType.REPLY


def _extract_address(raw: str | None) -> str | None:
    if not raw:
        return None
    if "<" in raw and ">" in raw:
        return raw.split("<", 1)[1].split(">", 1)[0].strip().lower() or None
    return raw.strip().lower() or None
