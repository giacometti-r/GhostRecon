from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from .common import OriginType


class CrmTargetStatus(StrEnum):
    PENDING_EXPORT = "pending_export"
    INVALIDATED = "invalidated"
    EXPORTED = "exported"


class CrmExportBatchStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RECONCILING = "reconciling"


class CrmExportItemStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"
    SKIPPED_POLICY = "skipped_policy"
    RECONCILED = "reconciled"


class CrmExportOperation(StrEnum):
    UPSERT_RECORD = "upsert_record"
    ADD_TO_LIST = "add_to_list"


class CrmTargetOut(BaseModel):
    id: str
    review_candidate_id: str | None = None
    review_decision_id: str | None = None
    target_type: str
    target_id: str
    display_name: str | None = None
    company_name: str | None = None
    email: str | None = None
    origin_type: OriginType | None = None
    origin_id: str | None = None
    source_definition_id: str | None = None
    source_item_ids: list[object] = []
    status: CrmTargetStatus
    export_status: str = "not_exported"
    policy_snapshot: dict[str, object] = {}
    approval_snapshot: dict[str, object] = {}
    version: int
    created_at: datetime
    updated_at: datetime


class CrmTargetList(BaseModel):
    crm_targets: list[CrmTargetOut]


class CrmTargetUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    status: CrmTargetStatus | None = None
    export_status: str | None = Field(default=None, max_length=64)


class CrmExportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crm_target_ids: list[str] = Field(min_length=1, max_length=100)
    provider: str = "attio"
    workspace_id: str | None = None
    reason: str | None = None


class CrmExportRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_ids: list[str] = []


class CrmExportItemOut(BaseModel):
    id: str
    batch_id: str
    crm_target_id: str
    target_type: str
    target_id: str
    operation: CrmExportOperation
    dependency_item_ids: list[object] = []
    provider_object: str
    provider_record_id: str | None = None
    provider_list_id: str | None = None
    provider_list_entry_id: str | None = None
    stable_match_key: str
    status: CrmExportItemStatus
    attempt_count: int
    last_error: str | None = None
    retry_after_seconds: int | None = None
    reconciliation_state: str = "not_required"
    created_at: datetime
    updated_at: datetime


class CrmExportBatchOut(BaseModel):
    id: str
    provider: str
    workspace_id: str | None = None
    requested_by: str
    status: CrmExportBatchStatus
    crm_target_ids: list[object] = []
    selection_hash: str
    idempotency_key: str
    counts: dict[str, object] = {}
    reconciliation_summary: dict[str, object] = {}
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[CrmExportItemOut] = []
