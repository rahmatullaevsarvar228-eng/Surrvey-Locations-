"""Time in one place.

* The database stores UTC timestamps ('YYYY-MM-DDTHH:MM:SS+00:00').
* Everything shown to the user (audit log window, reports, exports) is Tashkent time, UTC+5
  (Uzbekistan has no daylight saving time), formatted dd.mm.yyyy HH:MM:SS.
* Fixed-date mode (screenshots, demonstrations): ITTKI_TODAY=2026-10-11 or `--today 11.10.2026`
  makes "today" that date and the clock start at 10:00:00 Tashkent time on it, one second per call.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

TASHKENT = timezone(timedelta(hours=5), "UTC+5")
FMT = "%d.%m.%Y %H:%M:%S"

_fixed_today: Optional[date] = None
_fixed_now: Optional[datetime] = None      # next value returned by utc_now() in fixed mode


def parse_day(s: str) -> date:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"date expected (dd.mm.yyyy or yyyy-mm-dd): {s!r}")


def set_fixed(day: Optional[date], start: time = time(10, 0, 0)):
    """Freeze 'today' at `day`; the clock starts at `start` Tashkent time. None = real time."""
    global _fixed_today, _fixed_now
    _fixed_today = day
    _fixed_now = (datetime.combine(day, start, TASHKENT).astimezone(timezone.utc) if day else None)


def set_now(moment: Optional[datetime]):
    """Tests: the next utc_now() returns `moment` (aware), then +1 s per call."""
    global _fixed_now
    _fixed_now = moment.astimezone(timezone.utc) if moment else None


def fixed() -> bool:
    return _fixed_today is not None


def today() -> date:
    return _fixed_today or datetime.now(TASHKENT).date()


def utc_now() -> datetime:
    global _fixed_now
    if _fixed_now is not None:
        out = _fixed_now
        _fixed_now = out + timedelta(seconds=1)
        return out
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_iso() -> str:
    return utc_now().isoformat(timespec="seconds")


def to_tashkent(stamp: str) -> datetime:
    """Stored timestamp -> Tashkent time. Values without an offset were written by versions before the
    UTC change in the computer's local time, so they are interpreted as local time."""
    dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.astimezone()          # naive = local time of the machine that wrote it
    return dt.astimezone(TASHKENT)


def fmt_tashkent(stamp: Optional[str]) -> str:
    return to_tashkent(stamp).strftime(FMT) if stamp else ""


def now_tashkent() -> str:
    """Current Tashkent time for report headers (does not advance the fixed clock)."""
    if _fixed_now is not None:
        return _fixed_now.astimezone(TASHKENT).strftime(FMT)
    return datetime.now(TASHKENT).strftime(FMT)


def init_from_env(argv=None):
    """`--today dd.mm.yyyy` argument or ITTKI_TODAY environment variable."""
    argv = list(argv or [])
    value = None
    if "--today" in argv:
        i = argv.index("--today")
        if i + 1 < len(argv):
            value = argv[i + 1]
    value = value or os.environ.get("ITTKI_TODAY")
    if value:
        set_fixed(parse_day(value))
