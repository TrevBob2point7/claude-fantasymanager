from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import DataType, PlatformType, SyncStatus


class SyncResponse(BaseModel):
    status: str
    synced: list[str]
    errors: list[str]


class SyncLogRead(BaseModel):
    id: UUID
    platform_type: PlatformType
    data_type: DataType
    status: SyncStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
