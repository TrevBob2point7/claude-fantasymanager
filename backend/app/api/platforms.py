import xml.etree.ElementTree as ET
from datetime import date
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import get_db
from app.models.enums import PlatformType
from app.models.platform_account import PlatformAccount
from app.models.user import User
from app.schemas.platform_account import (
    MFLLoginRequest,
    PlatformAccountCreate,
    PlatformAccountRead,
)

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


def _mfl_year() -> int:
    """Return the current MFL season year (previous year if before March)."""
    today = date.today()
    return today.year if today.month >= 3 else today.year - 1


@router.post(
    "/accounts/mfl/login",
    response_model=PlatformAccountRead,
    status_code=status.HTTP_201_CREATED,
)
async def mfl_login(
    body: MFLLoginRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check if MFL account already linked
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.user_id == current_user.id,
            PlatformAccount.platform_type == PlatformType.mfl,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MFL account already linked",
        )

    year = _mfl_year()
    login_url = f"https://api.myfantasyleague.com/{year}/login"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            login_url,
            data={"USERNAME": body.username, "PASSWORD": body.password, "XML": "1"},
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="MFL API request failed",
        )

    root = ET.fromstring(resp.text)
    status_el = root if root.tag == "status" else root.find("status")
    if status_el is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected MFL response format",
        )

    cookie_value = status_el.get("cookie_value", "")
    if not cookie_value:
        error_msg = status_el.get("error", "Invalid MFL credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_msg,
        )

    account = PlatformAccount(
        user_id=current_user.id,
        platform_type=PlatformType.mfl,
        platform_username=body.username,
        credentials_json={"cookie": f"MFL_USER_ID={cookie_value}"},
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
