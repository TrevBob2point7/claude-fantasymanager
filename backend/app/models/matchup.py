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


class Matchup(Base):
    __tablename__ = "matchups"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    league_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("leagues.id"), nullable=False
    )
    week: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    home_user_league_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_leagues.id"), nullable=False
    )
    away_user_league_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_leagues.id"), nullable=False
    )
    home_score: Mapped[decimal.Decimal | None] = mapped_column(sa.Numeric(10, 2), nullable=True)
    away_score: Mapped[decimal.Decimal | None] = mapped_column(sa.Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    league: Mapped[League] = relationship(back_populates="matchups")
    home_user_league: Mapped[UserLeague] = relationship(foreign_keys=[home_user_league_id])
    away_user_league: Mapped[UserLeague] = relationship(foreign_keys=[away_user_league_id])
