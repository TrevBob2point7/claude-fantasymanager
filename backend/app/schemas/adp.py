from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ADPSourceRead(BaseModel):
    source: str
    adp: Decimal

    model_config = ConfigDict(from_attributes=True)


class PlayerADPRead(BaseModel):
    id: UUID
    player_id: UUID
    source: str
    format: str
    season: int
    adp: Decimal
    position_rank: int | None

    model_config = ConfigDict(from_attributes=True)


class BatchADPRequest(BaseModel):
    player_ids: list[UUID]
    season: int
    format: str | None = None


class ADPSyncResponse(BaseModel):
    synced: int
    skipped: int
    errored: int
