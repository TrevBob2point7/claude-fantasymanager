from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DataType, PlatformType, SyncStatus

if TYPE_CHECKING:
    from app.models.user import User


class SyncLog(Base):
    __tablename__ = "sync_log"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("users.id"), nullable=False)
    platform_type: Mapped[PlatformType] = mapped_column(
        sa.Enum(PlatformType, name="platformtype", create_type=False), nullable=False
    )
    data_type: Mapped[DataType] = mapped_column(sa.Enum(DataType, name="datatype"), nullable=False)
    status: Mapped[SyncStatus] = mapped_column(
        sa.Enum(SyncStatus, name="syncstatus"),
        server_default=sa.text("'pending'"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="sync_logs")
