from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import LeagueType, PlatformType, ScoringType

if TYPE_CHECKING:
    from app.models.matchup import Matchup
    from app.models.player_score import PlayerScore
    from app.models.projected_score import ProjectedScore
    from app.models.standing import Standing
    from app.models.transaction import Transaction
    from app.models.user_league import UserLeague


class League(Base):
    __tablename__ = "leagues"
    __table_args__ = (sa.UniqueConstraint("platform_type", "platform_league_id", "season"),)

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    platform_type: Mapped[PlatformType] = mapped_column(
        sa.Enum(PlatformType, name="platformtype", create_type=False), nullable=False
    )
    platform_league_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    season: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    roster_size: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    scoring_type: Mapped[ScoringType | None] = mapped_column(
        sa.Enum(ScoringType, name="scoringtype"), nullable=True
    )
    league_type: Mapped[LeagueType | None] = mapped_column(
        sa.Enum(LeagueType, name="leaguetype"), nullable=True
    )
    settings_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    user_leagues: Mapped[list[UserLeague]] = relationship(back_populates="league")
    standings: Mapped[list[Standing]] = relationship(back_populates="league")
    matchups: Mapped[list[Matchup]] = relationship(back_populates="league")
    player_scores: Mapped[list[PlayerScore]] = relationship(back_populates="league")
    projected_scores: Mapped[list[ProjectedScore]] = relationship(back_populates="league")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="league")
