from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import PlatformType


class PlatformAccountCreate(BaseModel):
    platform_type: PlatformType
    platform_username: str | None = None
    platform_user_id: str | None = None
    credentials_json: dict | None = None


class PlatformAccountRead(BaseModel):
    id: UUID
    platform_type: PlatformType
    platform_username: str | None
    platform_user_id: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
