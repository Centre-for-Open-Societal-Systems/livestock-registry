"""Today's date where the registry works.

The server runs in UTC. Between 00:00 and 03:00 in Ethiopia the UTC date is
still yesterday, so the default registration date ("today") was refused as
"in the future" by a check that compared with the UTC date. Every "not in the
future" check and every "today" default reads the date here instead.

Ethiopia has no daylight saving, so a fixed UTC+3 stands in when the time-zone
database is not installed.
"""

from datetime import date, datetime, timedelta, timezone

REGISTRY_TIME_ZONE = "Africa/Addis_Ababa"
_FALLBACK = timezone(timedelta(hours=3))


def _zone():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(REGISTRY_TIME_ZONE)
    except Exception:  # missing tzdata: ZoneInfoNotFoundError or an import problem
        return _FALLBACK


def local_today(now: datetime | None = None) -> date:
    """The registry's date. `now` (timezone-aware, or naive meaning UTC) is for tests."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(_zone()).date()
