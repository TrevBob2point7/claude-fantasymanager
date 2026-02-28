from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.user_league import UserLeague


class Roster(Base):
    __tablename__ = "rosters"
    __table_args__ = (sa.UniqueConstraint("user_league_id", "player_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    user_league_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_leagues.id"), nullable=False
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("players.id"), nullable=False
    )
    slot: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    acquired_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    user_league: Mapped[UserLeague] = relationship(back_populates="rosters")
    player: Mapped[Player] = relationship(back_populates="rosters")
