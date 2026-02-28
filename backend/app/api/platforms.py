from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db
from app.models.platform_account import PlatformAccount
from app.models.user import User
from app.schemas.platform_account import PlatformAccountCreate, PlatformAccountRead

router = APIRouter(prefix="/api/platforms", tags=["platforms"])


@router.post("/accounts", response_model=PlatformAccountRead, status_code=status.HTTP_201_CREATED)
async def create_platform_account(
    body: PlatformAccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.user_id == current_user.id,
            PlatformAccount.platform_type == body.platform_type,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Platform account already linked",
        )

    account = PlatformAccount(
        user_id=current_user.id,
        platform_type=body.platform_type,
        platform_username=body.platform_username,
        platform_user_id=body.platform_user_id,
        credentials_json=body.credentials_json,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/accounts", response_model=list[PlatformAccountRead])
async def list_platform_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.user_id == current_user.id)
    )
    return result.scalars().all()


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform_account(
    account_id: UUID,
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

    await db.delete(account)
    await db.commit()
