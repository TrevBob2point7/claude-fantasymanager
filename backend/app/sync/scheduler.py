import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.models import PlatformAccount, User
from app.sync.engine import SyncEngine

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def sync_all_users() -> None:
    """Background job: sync all users' platform accounts."""
    logger.info("Background sync started at %s", datetime.now(UTC))
    async with async_session() as db:
        result = await db.execute(
            select(PlatformAccount).join(User, User.id == PlatformAccount.user_id)
        )
        accounts = result.scalars().all()

        if not accounts:
            logger.info("No platform accounts to sync")
            return

        season = datetime.now(UTC).year
        engine = SyncEngine(db)

        for account in accounts:
            try:
                logger.info(
                    "Syncing account %s (user=%s, platform=%s)",
                    account.id,
                    account.user_id,
                    account.platform_type.value,
                )
                await engine.sync_all(account.user_id, account, season)
            except Exception:
                logger.exception("Background sync failed for account %s", account.id)

    logger.info("Background sync completed at %s", datetime.now(UTC))


def start_scheduler() -> None:
    """Start the background sync scheduler."""
    if not settings.SYNC_ENABLED:
        logger.info("Background sync is disabled (SYNC_ENABLED=false)")
        return

    scheduler.add_job(
        sync_all_users,
        "interval",
        minutes=settings.SYNC_INTERVAL_MINUTES,
        id="sync_all_users",
        replace_existing=True,
    )
    if scheduler.running:
        return
    scheduler.start()
    logger.info(
        "Background sync scheduler started (interval=%d minutes)",
        settings.SYNC_INTERVAL_MINUTES,
    )


def stop_scheduler() -> None:
    """Stop the background sync scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background sync scheduler stopped")
