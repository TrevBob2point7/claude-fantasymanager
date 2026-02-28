from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.league import League
    from app.models.roster import Roster
    from app.models.standing import Standing
    from app.models.user import User


class UserLeague(Base):
    __tablename__ = "user_leagues"
    __table_args__ = (sa.UniqueConstraint("user_id", "league_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("users.id"), nullable=False)
    league_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("leagues.id"), nullable=False
    )
    team_name: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    platform_team_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="user_leagues")
    league: Mapped[League] = relationship(back_populates="user_leagues")
    rosters: Mapped[list[Roster]] = relationship(back_populates="user_league")
    standings: Mapped[list[Standing]] = relationship(back_populates="user_league")
