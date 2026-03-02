from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import LeagueType, PlatformType, ScoringType, TransactionType


class DiscoverRequest(BaseModel):
    platform_account_id: UUID
    season: int | None = None


class DiscoveredLeague(BaseModel):
    platform_league_id: str
    name: str
    season: int
    roster_size: int | None
    scoring_type: str | None
    already_linked: bool


class LeagueRead(BaseModel):
    id: UUID
    platform_type: PlatformType
    platform_league_id: str
    name: str
    season: int
    roster_size: int | None
    scoring_type: ScoringType | None
    league_type: LeagueType | None = None
    team_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StandingRead(BaseModel):
    id: UUID
    team_name: str | None
    wins: int
    losses: int
    ties: int
    points_for: Decimal
    points_against: Decimal
    rank: int | None
    is_me: bool = False

    model_config = ConfigDict(from_attributes=True)


class RosterEntryRead(BaseModel):
    id: UUID
    player_id: UUID
    player_name: str
    position: str | None
    team: str | None
    slot: str | None
    status: str | None = None
    bye_week: int | None = None

    model_config = ConfigDict(from_attributes=True)


class MatchupPlayerRead(BaseModel):
    player_id: str
    name: str
    position: str | None = None
    points: float | None = None


class MatchupRead(BaseModel):
    id: UUID
    week: int
    home_team_name: str | None
    away_team_name: str | None
    home_score: Decimal | None
    away_score: Decimal | None
    is_user_matchup: bool = False
    home_starters: list[MatchupPlayerRead] | None = None
    away_starters: list[MatchupPlayerRead] | None = None

    model_config = ConfigDict(from_attributes=True)


class TransactionRead(BaseModel):
    id: UUID
    type: TransactionType
    player_name: str | None
    from_team_name: str | None
    to_team_name: str | None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class LeagueSeasonRead(BaseModel):
    season: int
    league_id: UUID


class LeagueSeasonsResponse(BaseModel):
    seasons: list[LeagueSeasonRead]


class LeagueDetailRead(BaseModel):
    id: UUID
    platform_type: PlatformType
    platform_league_id: str
    name: str
    season: int
    roster_size: int | None
    scoring_type: ScoringType | None
    league_type: LeagueType | None = None
    team_name: str | None = None
    current_week: int | None = None
    created_at: datetime
    standings: list[StandingRead]
    roster: list[RosterEntryRead]
    recent_matchups: list[MatchupRead]
    recent_transactions: list[TransactionRead]
