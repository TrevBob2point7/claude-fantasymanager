import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adp.sync import ADPSyncService
from app.auth import get_current_user
from app.core.database import get_db
from app.models.player_adp import PlayerADP
from app.models.user import User
from app.schemas.adp import ADPSyncResponse, PlayerADPRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/adp", tags=["adp"])


@router.post("/sync", response_model=ADPSyncResponse)
async def sync_adp(
    season: int = Query(default_factory=lambda: datetime.now(UTC).year),
    sources: list[str] | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an ADP sync for the given season."""
    service = ADPSyncService(db)
    result = await service.sync_adp(season=season, sources=sources)
    return ADPSyncResponse(**result)


@router.get("/players/{player_id}/history", response_model=list[PlayerADPRead])
async def get_player_adp_history(
    player_id: UUID,
    format: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ADP history for a player across seasons."""
    query = select(PlayerADP).where(PlayerADP.player_id == player_id)
    if format:
        query = query.where(PlayerADP.format == format)
    query = query.order_by(PlayerADP.season.desc(), PlayerADP.source)

    result = await db.execute(query)
    entries = result.scalars().all()
    return [PlayerADPRead.model_validate(e) for e in entries]
