from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
