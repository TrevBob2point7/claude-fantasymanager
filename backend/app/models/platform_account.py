from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import PlatformType

if TYPE_CHECKING:
    from app.models.user import User


class PlatformAccount(Base):
    __tablename__ = "platform_accounts"
    __table_args__ = (sa.UniqueConstraint("user_id", "platform_type"),)

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("users.id"), nullable=False)
    platform_type: Mapped[PlatformType] = mapped_column(
        sa.Enum(PlatformType, name="platformtype"), nullable=False
    )
    platform_username: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    platform_user_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    credentials_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="platform_accounts")
