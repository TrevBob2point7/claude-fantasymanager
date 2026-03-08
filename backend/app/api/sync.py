import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db, async_session
from app.models import PlatformAccount, SyncLog
from app.models.user import User
from app.schemas.sync import SyncLogRead, SyncResponse
from app.sync.engine import SyncEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


async def _run_sync(user_id: UUID, account_id: UUID, season: int) -> None:
    """Run sync in a background task with its own DB session."""
    async with async_session() as db:
        result = await db.execute(
            select(PlatformAccount).where(PlatformAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        if account is None:
            logger.error("Background sync: account %s not found", account_id)
            return

        engine = SyncEngine(db)
        try:
            await engine.sync_all(user_id, account, season)
            logger.info("Background sync completed for account %s season %d", account_id, season)
        except Exception:
            logger.exception("Background sync failed for account %s season %d", account_id, season)


@router.post("/{account_id}", response_model=SyncResponse)
async def trigger_sync(
    account_id: UUID,
    background_tasks: BackgroundTasks,
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

    background_tasks.add_task(_run_sync, current_user.id, account_id, season)
    return SyncResponse(status="ok", synced=["sync started in background"], errors=[])


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
