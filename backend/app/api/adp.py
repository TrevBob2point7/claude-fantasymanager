import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adp.sync import ADPSyncService
from app.auth import get_current_user
from app.core.database import get_db
from app.models.player_adp import PlayerADP
from app.models.user import User
from app.schemas.adp import ADPSyncResponse, BatchADPRequest, PlayerADPRead

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


@router.post("/batch", response_model=dict[str, Decimal | None])
async def get_batch_adp(
    body: BatchADPRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ADP values for a batch of players."""
    if not body.player_ids:
        return {}

    # Find the closest available ADP season
    season_result = await db.execute(
        select(PlayerADP.season)
        .where(PlayerADP.player_id.in_(body.player_ids))
        .order_by(sa.func.abs(PlayerADP.season - body.season))
        .limit(1)
    )
    adp_season = season_result.scalar_one_or_none() or body.season

    # Preferred source order: pick the first available per player rather
    # than min() across sources, which can mix incompatible scales.
    source_priority = case(
        {"sleeper": 1, "ffc": 2, "dynastyprocess": 3},
        value=PlayerADP.source,
        else_=99,
    )

    filters = [
        PlayerADP.player_id.in_(body.player_ids),
        PlayerADP.season == adp_season,
    ]
    if body.format:
        filters.append(PlayerADP.format == body.format)

    adp_query = (
        select(PlayerADP.player_id, PlayerADP.adp)
        .where(*filters)
        .distinct(PlayerADP.player_id)
        .order_by(PlayerADP.player_id, source_priority)
    )

    result = await db.execute(adp_query)
    return {str(pid): adp for pid, adp in result.all()}


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
