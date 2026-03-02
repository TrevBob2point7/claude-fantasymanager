from datetime import UTC, datetime


def get_current_nfl_season() -> int:
    """Return the current NFL season year.

    The NFL season starts in September, so before September we still
    consider the previous calendar year to be the current season
    (e.g. March 2026 → 2025).
    """
    now = datetime.now(UTC)
    return now.year if now.month >= 9 else now.year - 1
