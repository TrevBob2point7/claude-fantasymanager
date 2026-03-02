from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ADPFormat

if TYPE_CHECKING:
    from app.models.player import Player


class PlayerADP(Base):
    __tablename__ = "player_adp"
    __table_args__ = (
        sa.UniqueConstraint("player_id", "source", "format", "season"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("players.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    format: Mapped[ADPFormat] = mapped_column(
        sa.Enum(ADPFormat, name="adpformat"), nullable=False
    )
    season: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    adp: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2), nullable=False)
    position_rank: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    player: Mapped[Player] = relationship(back_populates="adp_entries")
