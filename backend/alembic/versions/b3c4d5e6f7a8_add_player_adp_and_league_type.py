"""add player_adp table and league_type column

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-02-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums via DO blocks (PG <17 lacks CREATE TYPE IF NOT EXISTS),
    # then reference with create_type=False to prevent SQLAlchemy's
    # create_table from trying to CREATE TYPE again.
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE adpformat AS ENUM ('standard', 'half_ppr', 'ppr', 'superflex', 'dynasty', 'two_qb');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE leaguetype AS ENUM ('redraft', 'keeper', 'dynasty');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    # Use postgresql.ENUM with create_type=False to prevent SQLAlchemy's
    # create_table from trying to CREATE TYPE again.
    from sqlalchemy.dialects import postgresql
    adpformat_type = postgresql.ENUM(
        "standard", "half_ppr", "ppr", "superflex", "dynasty", "two_qb",
        name="adpformat",
        create_type=False,
    )
    leaguetype_type = postgresql.ENUM(
        "redraft", "keeper", "dynasty",
        name="leaguetype",
        create_type=False,
    )

    # Create player_adp table
    op.create_table(
        "player_adp",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("format", adpformat_type, nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("adp", sa.Numeric(8, 2), nullable=False),
        sa.Column("position_rank", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.UniqueConstraint("player_id", "source", "format", "season"),
    )

    # Add league_type column to leagues
    op.add_column(
        "leagues",
        sa.Column("league_type", leaguetype_type, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("leagues", "league_type")
    op.drop_table("player_adp")

    sa.Enum(name="leaguetype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="adpformat").drop(op.get_bind(), checkfirst=True)
