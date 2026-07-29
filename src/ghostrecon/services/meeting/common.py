from __future__ import annotations

from datetime import UTC, datetime

MEETING_SERVICE_NAME = "meeting-handoff-service"


SEQUENCING_SERVICE_NAME = "sequencing-service"


ACTIVE_ENROLLMENT_STATUSES = {"active"}


def utcnow() -> datetime:
    return datetime.now(UTC)
