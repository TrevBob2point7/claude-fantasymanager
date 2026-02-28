from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.platform_account import PlatformAccount
    from app.models.sync_log import SyncLog
    from app.models.user_league import UserLeague


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(sa.String(320), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    platform_accounts: Mapped[list[PlatformAccount]] = relationship(back_populates="user")
    user_leagues: Mapped[list[UserLeague]] = relationship(back_populates="user")
    sync_logs: Mapped[list[SyncLog]] = relationship(back_populates="user")
