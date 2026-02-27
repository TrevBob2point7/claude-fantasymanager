import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db
from app.models import PlatformAccount, SyncLog
from app.models.user import User
from app.schemas.sync import SyncLogRead, SyncResponse
from app.sync.engine import SyncEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/{account_id}", response_model=SyncResponse)
async def trigger_sync(
    account_id: UUID,
    season: int = Query(2025, ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.id == account_id,
            PlatformAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform account not found",
        )

    engine = SyncEngine(db)
    result_data = await engine.sync_all(current_user.id, account, season)
    return SyncResponse(**result_data)


@router.get("/log", response_model=list[SyncLogRead])
async def get_sync_log(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SyncLog)
        .where(SyncLog.user_id == current_user.id)
        .order_by(SyncLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
