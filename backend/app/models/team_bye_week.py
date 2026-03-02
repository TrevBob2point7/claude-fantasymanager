from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TeamByeWeek(Base):
    __tablename__ = "team_bye_weeks"
    __table_args__ = (sa.UniqueConstraint("season", "team"),)

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    season: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    team: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    bye_week: Mapped[int] = mapped_column(sa.Integer, nullable=False)
