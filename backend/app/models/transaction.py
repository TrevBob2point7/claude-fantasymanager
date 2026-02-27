from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TransactionType

if TYPE_CHECKING:
    from app.models.league import League
    from app.models.player import Player
    from app.models.user_league import UserLeague


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    league_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("leagues.id"), nullable=False
    )
    type: Mapped[TransactionType] = mapped_column(
        sa.Enum(TransactionType, name="transactiontype"), nullable=False
    )
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("players.id"), nullable=True
    )
    from_user_league_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_leagues.id"), nullable=True
    )
    to_user_league_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_leagues.id"), nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
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

    league: Mapped[League] = relationship(back_populates="transactions")
    player: Mapped[Player] = relationship()
    from_user_league: Mapped[UserLeague] = relationship(foreign_keys=[from_user_league_id])
    to_user_league: Mapped[UserLeague] = relationship(foreign_keys=[to_user_league_id])
