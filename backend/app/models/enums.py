import enum


class PlatformType(enum.StrEnum):
    sleeper = "sleeper"
    mfl = "mfl"
    espn = "espn"


class Position(enum.StrEnum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"
    K = "K"
    DEF = "DEF"
    DL = "DL"
    LB = "LB"
    DB = "DB"
    FLEX = "FLEX"
    SUPERFLEX = "SUPERFLEX"
    BENCH = "BENCH"
    IR = "IR"


class ScoringType(enum.StrEnum):
    standard = "standard"
    half_ppr = "half_ppr"
    ppr = "ppr"
    custom = "custom"


class PlayerStatus(enum.StrEnum):
    active = "active"
    injured_reserve = "injured_reserve"
    out = "out"
    questionable = "questionable"
    doubtful = "doubtful"
    suspended = "suspended"


class TransactionType(enum.StrEnum):
    add = "add"
    drop = "drop"
    trade = "trade"
    waiver = "waiver"


class SyncStatus(enum.StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class LeagueType(enum.StrEnum):
    redraft = "redraft"
    keeper = "keeper"
    dynasty = "dynasty"


class ADPFormat(enum.StrEnum):
    standard = "standard"
    half_ppr = "half_ppr"
    ppr = "ppr"
    superflex = "superflex"
    dynasty = "dynasty"
    two_qb = "two_qb"


class DataType(enum.StrEnum):
    leagues = "leagues"
    rosters = "rosters"
    matchups = "matchups"
    standings = "standings"
    players = "players"
    transactions = "transactions"
