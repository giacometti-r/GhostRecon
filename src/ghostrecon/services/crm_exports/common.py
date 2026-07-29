from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

CRM_SERVICE_NAME = "crm-service"


EXPORTABLE_TARGET_STATUS = "pending_export"


EXPORTABLE_EXPORT_STATUSES = {"not_exported", "failed_retryable"}


SUCCESS_ITEM_STATUSES = {"succeeded", "reconciled"}


def selection_hash(target_ids: list[str]) -> str:
    payload = json.dumps(sorted(target_ids), separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC)
