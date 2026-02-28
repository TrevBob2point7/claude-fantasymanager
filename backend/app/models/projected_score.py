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
    from app.models.player import Player


class ProjectedScore(Base):
    __tablename__ = "projected_scores"
    __table_args__ = (sa.UniqueConstraint("player_id", "league_id", "week", "season"),)

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("players.id"), nullable=False
    )
    league_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("leagues.id"), nullable=False
    )
    week: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    season: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    projected_points: Mapped[decimal.Decimal | None] = mapped_column(
        sa.Numeric(10, 2), nullable=True
    )
    source: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    player: Mapped[Player] = relationship(back_populates="projected_scores")
    league: Mapped[League] = relationship(back_populates="projected_scores")
