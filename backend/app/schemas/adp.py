from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import ADPFormat


class ADPSourceRead(BaseModel):
    source: str
    adp: Decimal

    model_config = ConfigDict(from_attributes=True)


class PlayerADPRead(BaseModel):
    id: UUID
    player_id: UUID
    source: str
    format: ADPFormat
    season: int
    adp: Decimal
    position_rank: int | None

    model_config = ConfigDict(from_attributes=True)


class BatchADPRequest(BaseModel):
    player_ids: list[UUID]
    season: int
    format: ADPFormat | None = None


class ADPSyncResponse(BaseModel):
    synced: int
    skipped: int
    errored: int
