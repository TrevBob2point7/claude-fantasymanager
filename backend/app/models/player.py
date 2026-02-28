from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import PlayerStatus, Position

if TYPE_CHECKING:
    from app.models.player_score import PlayerScore
    from app.models.projected_score import ProjectedScore
    from app.models.roster import Roster


class Player(Base):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    full_name: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    position: Mapped[Position | None] = mapped_column(
        sa.Enum(Position, name="playerposition"), nullable=True
    )
    team: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    sleeper_id: Mapped[str | None] = mapped_column(sa.String(50), unique=True, nullable=True)
    mfl_id: Mapped[str | None] = mapped_column(sa.String(50), unique=True, nullable=True)
    espn_id: Mapped[str | None] = mapped_column(sa.String(50), unique=True, nullable=True)
    status: Mapped[PlayerStatus | None] = mapped_column(
        sa.Enum(PlayerStatus, name="playerstatus"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    rosters: Mapped[list[Roster]] = relationship(back_populates="player")
    player_scores: Mapped[list[PlayerScore]] = relationship(back_populates="player")
    projected_scores: Mapped[list[ProjectedScore]] = relationship(back_populates="player")
