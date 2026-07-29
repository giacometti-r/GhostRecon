from uuid import UUID

from pydantic import (
    BaseModel,
)


class JobAccepted(BaseModel):
    job_id: UUID
    status: str = "accepted"
