from dataclasses import dataclass, field


@dataclass
class PlatformUser:
    user_id: str
    username: str
    display_name: str | None = None


@dataclass
class PlatformLeagueUser:
    user_id: str  # platform user ID (e.g. Sleeper owner_id)
    display_name: str | None = None
    team_name: str | None = None


@dataclass
class PlatformLeague:
    league_id: str
    name: str
    season: int
    roster_size: int | None = None
    scoring_type: str | None = None
    league_type: str | None = None
    settings: dict | None = None
    previous_league_id: str | None = None
    roster_positions: list[str] | None = None


@dataclass
class PlatformRosterEntry:
    owner_id: str  # platform user ID (e.g. Sleeper owner_id)
    roster_id: str = ""  # platform roster/team ID (e.g. Sleeper roster_id, 1-12)
    player_ids: list[str] = field(default_factory=list)
    starters: list[str] = field(default_factory=list)
    taxi: list[str] = field(default_factory=list)


@dataclass
class PlatformMatchup:
    matchup_id: int
    roster_id: str
    points: float | None = None
    week: int = 0
    starters: list[str] = field(default_factory=list)
    starters_points: dict[str, float] = field(default_factory=dict)


@dataclass
class PlatformTransaction:
    type: str  # "add", "drop", "trade", "waiver"
    player_ids_added: list[str] = field(default_factory=list)
    player_ids_dropped: list[str] = field(default_factory=list)
    roster_ids: list[str] = field(default_factory=list)
    timestamp: int = 0  # unix millis
