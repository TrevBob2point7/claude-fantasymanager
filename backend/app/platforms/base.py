from abc import ABC, abstractmethod

from app.platforms.schemas import (
    PlatformLeague,
    PlatformMatchup,
    PlatformRosterEntry,
    PlatformTransaction,
    PlatformUser,
)


class PlatformAdapter(ABC):
    @abstractmethod
    async def get_user(self, username: str) -> PlatformUser: ...

    @abstractmethod
    async def get_league(self, league_id: str) -> PlatformLeague: ...

    @abstractmethod
    async def get_leagues(self, user_id: str, season: int) -> list[PlatformLeague]: ...

    @abstractmethod
    async def get_rosters(self, league_id: str) -> list[PlatformRosterEntry]: ...

    @abstractmethod
    async def get_matchups(self, league_id: str, week: int) -> list[PlatformMatchup]: ...

    @abstractmethod
    async def get_transactions(self, league_id: str, week: int) -> list[PlatformTransaction]: ...
