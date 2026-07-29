from sqlalchemy.ext.asyncio import AsyncSession

from .contact_repository import ContactRepositoryMixin
from .domain_repository import DomainDiscoveryRepositoryMixin
from .email_repository import EmailRepositoryMixin
from .entity_repository import EntityResolutionRepositoryMixin
from .review_repository import ReviewRepositoryMixin


class EnrichmentWorkflowRepository(
    EntityResolutionRepositoryMixin,
    ContactRepositoryMixin,
    DomainDiscoveryRepositoryMixin,
    EmailRepositoryMixin,
    ReviewRepositoryMixin,
):
    def __init__(self, session: AsyncSession):
        self.session = session
