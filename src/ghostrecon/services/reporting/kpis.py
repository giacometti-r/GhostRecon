from __future__ import annotations

from ghostrecon.common.config import Settings
from ghostrecon.models.api import (
    DashboardRole,
    ReportingKpiCatalog,
    ReportingOperatorContext,
    SourceHealth,
)


async def get_reporting_kpi_catalog(
    *,
    operator: ReportingOperatorContext | None = None,
    settings: Settings | None = None,
) -> ReportingKpiCatalog:
    _ = operator
    metadata = await reporting_metadata(None, settings=settings)
    return ReportingKpiCatalog(metadata=metadata, kpis=KPI_CATALOG)


def project_source_health(
    source: SourceHealth,
    context: ReportingOperatorContext,
) -> SourceHealth:
    if context.role in {DashboardRole.GOVERNANCE_REVIEWER, DashboardRole.ADMINISTRATOR}:
        return source
    return source.model_copy(update={"checkpoint_state": {}, "last_error": None})


from .common import KPI_CATALOG, reporting_metadata  # noqa: E402
