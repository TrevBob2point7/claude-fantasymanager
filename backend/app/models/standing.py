from __future__ import annotations

import decimal
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.league import League
    from app.models.user_league import UserLeague


class Standing(Base):
    __tablename__ = "standings"
    __table_args__ = (sa.UniqueConstraint("league_id", "user_league_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    league_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("leagues.id"), nullable=False
    )
    user_league_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_leagues.id"), nullable=False
    )
    wins: Mapped[int] = mapped_column(sa.Integer, server_default=sa.text("0"), nullable=False)
    losses: Mapped[int] = mapped_column(sa.Integer, server_default=sa.text("0"), nullable=False)
    ties: Mapped[int] = mapped_column(sa.Integer, server_default=sa.text("0"), nullable=False)
    points_for: Mapped[decimal.Decimal] = mapped_column(
        sa.Numeric(10, 2), server_default=sa.text("0"), nullable=False
    )
    points_against: Mapped[decimal.Decimal] = mapped_column(
        sa.Numeric(10, 2), server_default=sa.text("0"), nullable=False
    )
    rank: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    league: Mapped[League] = relationship(back_populates="standings")
    user_league: Mapped[UserLeague] = relationship(back_populates="standings")
