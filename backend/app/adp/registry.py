from app.adp.base import ADPProvider
from app.adp.dynastyprocess import DynastyProcessADPProvider
from app.adp.ffc import FFCADPProvider
from app.adp.sleeper import SleeperADPProvider


def get_adp_providers() -> list[ADPProvider]:
    """Return all available ADP providers."""
    return [
        SleeperADPProvider(),
        FFCADPProvider(),
        DynastyProcessADPProvider(),
    ]
