from __future__ import annotations

from datetime import UTC, datetime

SEQUENCING_SERVICE_NAME = "sequencing-service"


ACTIVE_ENROLLMENT_STATUSES = {"active"}


TERMINAL_ENROLLMENT_STATUSES = {"completed", "canceled", "suppressed", "failed"}


def utcnow() -> datetime:
    return datetime.now(UTC)
