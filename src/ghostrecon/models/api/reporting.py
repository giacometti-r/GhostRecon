from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
)

from .crm import CrmTargetOut
from .events import CyberEventOut
from .incidents import SecurityIncidentOut, WatchTargetOut
from .review_contracts import ReviewCandidateOut
from .source_contracts import SourceHealth


class DashboardRole(StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    GOVERNANCE_REVIEWER = "governance_reviewer"
    ADMINISTRATOR = "administrator"


class ReportingOperatorContext(BaseModel):
    actor: str = "system"
    role: DashboardRole = DashboardRole.VIEWER


class ReportingMetadata(BaseModel):
    generated_at: datetime
    watermarks: dict[str, object] = {}
    projection_version: str
    stale: bool = False
    degraded_dependencies: list[str] = []


class ReportingEventList(BaseModel):
    metadata: ReportingMetadata
    events: list[CyberEventOut]
    next_cursor: str | None = None


class ReportingEventDetail(BaseModel):
    metadata: ReportingMetadata
    event: CyberEventOut


class ReportingIncidentList(BaseModel):
    metadata: ReportingMetadata
    incidents: list[SecurityIncidentOut]
    next_cursor: str | None = None


class ReportingIncidentDetail(BaseModel):
    metadata: ReportingMetadata
    incident: SecurityIncidentOut


class ReportingWatchTargetList(BaseModel):
    metadata: ReportingMetadata
    watch_targets: list[WatchTargetOut]
    next_cursor: str | None = None


class ReportingWatchTargetDetail(BaseModel):
    metadata: ReportingMetadata
    watch_target: WatchTargetOut


class ReportingReviewQueue(BaseModel):
    metadata: ReportingMetadata
    candidates: list[ReviewCandidateOut]
    next_cursor: str | None = None


class ReportingCrmTargetList(BaseModel):
    metadata: ReportingMetadata
    crm_targets: list[CrmTargetOut]
    next_cursor: str | None = None


class ReportingCrmTargetDetail(BaseModel):
    metadata: ReportingMetadata
    crm_target: CrmTargetOut


class ReportingSourceHealthList(BaseModel):
    metadata: ReportingMetadata
    sources: list[SourceHealth]
    next_cursor: str | None = None


class ReportingKpiCatalog(BaseModel):
    metadata: ReportingMetadata
    kpis: dict[str, list[str]]
