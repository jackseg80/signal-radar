"""NYSE sessions used by the live scanner and calendar strategies."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

import exchange_calendars as xcals
import pandas as pd


XNYS = xcals.get_calendar("XNYS")


def _stamp(value: date | str | pd.Timestamp) -> pd.Timestamp:
    """Return a timezone naive midnight timestamp for a session date."""
    return pd.Timestamp(value).tz_localize(None).normalize()


def session_month_progress(session: date | str | pd.Timestamp) -> tuple[int, int]:
    """Return one-based trading day and remaining sessions including today."""
    day = _stamp(session)
    if not XNYS.is_session(day):
        raise ValueError(f"{day.date()} is not an XNYS session")
    first = day.replace(day=1)
    last = day + pd.offsets.MonthEnd(0)
    sessions = XNYS.sessions_in_range(first, last)
    rank = int(sessions.get_loc(day)) + 1
    return rank, len(sessions) - rank + 1


def next_session(session: date | str | pd.Timestamp) -> str:
    """Return the next XNYS session date."""
    return str(XNYS.next_session(_stamp(session)).date())


def last_completed_session(now: datetime | None = None) -> str:
    """Return the most recent XNYS session whose official close has passed."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    current_utc = pd.Timestamp(current).tz_convert("UTC")
    today = current_utc.tz_convert("America/New_York").normalize().tz_localize(None)
    session = XNYS.date_to_session(today, direction="previous")
    if current_utc < XNYS.session_close(session):
        session = XNYS.previous_session(session)
    return str(session.date())


def session_open(session: date | str | pd.Timestamp) -> datetime:
    """Return the official XNYS open as an aware UTC datetime."""
    return XNYS.session_open(_stamp(session)).to_pydatetime()


def is_expired(target_session: str, now: datetime | None = None) -> bool:
    """An unfilled market-open recommendation expires when that open passes."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return current >= session_open(target_session)
