from sqlalchemy.ext.asyncio import AsyncSession

from .incident_repository import IncidentRepositoryMixin
from .repository_events import RepositoryEventsMixin
from .watchlist_repository import WatchlistRepositoryMixin


class IncidentIntelligenceRepository(
    IncidentRepositoryMixin, WatchlistRepositoryMixin, RepositoryEventsMixin
):
    def __init__(self, session: AsyncSession):
        self.session = session
