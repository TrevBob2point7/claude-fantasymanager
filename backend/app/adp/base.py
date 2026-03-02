from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.enums import ADPFormat


@dataclass
class ADPRecord:
    player_name: str
    position: str | None
    team: str | None
    adp: float
    position_rank: int | None = None
    sleeper_id: str | None = None
    source: str = ""
    format: ADPFormat = ADPFormat.standard


class ADPProvider(ABC):
    """Abstract base class for ADP data providers."""

    @abstractmethod
    async def fetch_adp(self, season: int, format: ADPFormat) -> list[ADPRecord]:
        """Fetch ADP data for a given season and format."""
        ...

    @abstractmethod
    def supported_formats(self) -> list[ADPFormat]:
        """Return the list of ADP formats this provider supports."""
        ...
