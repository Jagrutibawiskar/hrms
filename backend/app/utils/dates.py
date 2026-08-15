import calendar
from datetime import date, datetime, timedelta, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def today() -> date:
    return utcnow().date()


def date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def as_utc(dt: datetime | None) -> datetime | None:
    """Naive datetimes from SQLite come back tz-less; treat them as UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def hours_between(start: datetime, end: datetime) -> float:
    delta = as_utc(end) - as_utc(start)
    return round(max(delta.total_seconds(), 0) / 3600, 2)
