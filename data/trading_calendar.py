"""
NSE India Capital Market (Equity Cash) trading calendar.

Designed for the quant toolkit's NSE equity backtesting/data layer.

Features:
- NSE cash-market trading-day detection
- Weekend and official holiday handling
- Next/previous trading-day arithmetic
- Trading-day range/count operations
- Date alignment
- Holiday metadata
- Muhurat Trading metadata
- JSON import/export for updating future calendars

The 2025 and 2026 holiday data below is based on NSE Capital Market
trading-holiday circulars. Muhurat Trading is kept separate from the
ordinary full-day holiday set because NSE treats those dates as holidays
with a special trading session.

Sources:
- NSE Capital Market 2025 trading holidays: NSE/CMTR/65587
- NSE 2026 holidays page / NSE 2026 market holiday circular
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class Holiday:
    date: date
    name: str
    muhurat_trading: bool = False


# ---------------------------------------------------------------------------
# OFFICIAL NSE CAPITAL MARKET TRADING HOLIDAYS
# ---------------------------------------------------------------------------
#
# These are ordinary non-trading dates for the NSE equity cash market.
#
# Dates that fall on Saturday/Sunday are not included because weekends are
# already handled by is_weekend().
#
# Muhurat Trading dates are represented separately below.
# ---------------------------------------------------------------------------

_HOLIDAYS: tuple[Holiday, ...] = (
    # 2025
    Holiday(date(2025, 2, 26), "Mahashivratri"),
    Holiday(date(2025, 3, 14), "Holi"),
    Holiday(date(2025, 3, 31), "Id-Ul-Fitr (Ramadan Eid)"),
    Holiday(date(2025, 4, 10), "Shri Mahavir Jayanti"),
    Holiday(date(2025, 4, 14), "Dr. Baba Saheb Ambedkar Jayanti"),
    Holiday(date(2025, 4, 18), "Good Friday"),
    Holiday(date(2025, 5, 1), "Maharashtra Day"),
    Holiday(date(2025, 8, 15), "Independence Day"),
    Holiday(date(2025, 8, 27), "Ganesh Chaturthi"),
    Holiday(date(2025, 10, 2), "Mahatma Gandhi Jayanti / Dussehra"),
    Holiday(date(2025, 10, 22), "Diwali-Balipratipada"),
    Holiday(date(2025, 11, 5), "Prakash Gurpurb Sri Guru Nanak Dev"),
    Holiday(date(2025, 12, 25), "Christmas"),

    # 2026
    Holiday(date(2026, 1, 26), "Republic Day"),
    Holiday(date(2026, 3, 3), "Holi"),
    Holiday(date(2026, 3, 26), "Shri Ram Navami"),
    Holiday(date(2026, 3, 31), "Shri Mahavir Jayanti"),
    Holiday(date(2026, 4, 3), "Good Friday"),
    Holiday(date(2026, 4, 14), "Dr. Babasaheb Ambedkar Jayanti"),
    Holiday(date(2026, 5, 1), "Maharashtra Day"),
    Holiday(date(2026, 5, 28), "Bakri Id"),
    Holiday(date(2026, 6, 26), "Muharram"),
    Holiday(date(2026, 8, 26), "Id-E-Milad"),
    Holiday(date(2026, 9, 14), "Ganesh Chaturthi"),
    Holiday(date(2026, 10, 2), "Mahatma Gandhi Jayanti"),
    Holiday(date(2026, 10, 20), "Dussehra"),
    Holiday(date(2026, 11, 10), "Diwali-Balipratipada"),
    Holiday(date(2026, 11, 24), "Prakash Gurpurb Sri Guru Nanak Dev"),
    Holiday(date(2026, 12, 25), "Christmas"),
)

# Special sessions held on dates otherwise designated as holidays.
# NSE has stated that Muhurat Trading will be conducted on these dates.
_MUHURAT_DATES: dict[date, str] = {
    date(2025, 10, 21): "Diwali Laxmi Pujan",
    date(2026, 11, 8): "Diwali Laxmi Pujan",
}

# Holidays that fall on weekends are kept as metadata for completeness.
# They do NOT need to be added to the weekday holiday set.
_WEEKEND_HOLIDAYS: dict[date, str] = {
    date(2025, 1, 26): "Republic Day",
    date(2026, 2, 15): "Mahashivratri",
    date(2026, 3, 21): "Id-Ul-Fitr (Ramadan Eid)",
    date(2026, 8, 15): "Independence Day",
}


def _to_date(value: str | date | datetime) -> date:
    """Normalize input to a date."""
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(
                f"Invalid date {value!r}; expected YYYY-MM-DD."
            ) from exc

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    raise TypeError(
        f"Expected str, date, or datetime; got {type(value).__name__}."
    )


def _build_holiday_map() -> dict[date, Holiday]:
    return {item.date: item for item in _HOLIDAYS}


class TradingCalendar:
    """NSE India Capital Market / Equity Cash trading calendar."""

    def __init__(
        self,
        holidays: dict[date, Holiday] | None = None,
        muhurat_dates: dict[date, str] | None = None,
    ) -> None:
        self._holidays = (
            dict(holidays)
            if holidays is not None
            else _build_holiday_map()
        )

        self._muhurat_dates = (
            dict(muhurat_dates)
            if muhurat_dates is not None
            else dict(_MUHURAT_DATES)
        )

    # ------------------------------------------------------------------
    # Core queries
    # ------------------------------------------------------------------

    def is_weekend(self, day: str | date | datetime) -> bool:
        return _to_date(day).weekday() >= 5

    def is_holiday(self, day: str | date | datetime) -> bool:
        d = _to_date(day)
        return d in self._holidays or d in self._muhurat_dates

    def is_muhurat_trading_day(self, day: str | date | datetime) -> bool:
        return _to_date(day) in self._muhurat_dates

    def is_trading_day(self, day: str | date | datetime) -> bool:
        """
        Return whether the date has a normal NSE cash-market session.

        Muhurat dates return False because they are special sessions rather
        than ordinary trading days. This prevents normal daily backtests
        from silently treating a special session as a normal session.
        """
        d = _to_date(day)

        if self.is_weekend(d):
            return False

        if self.is_holiday(d):
            return False

        return True

    def is_any_trading_session(self, day: str | date | datetime) -> bool:
        """Return True for normal sessions OR Muhurat Trading sessions."""
        d = _to_date(day)

        if self.is_weekend(d):
            return d in self._muhurat_dates

        return self.is_trading_day(d) or self.is_muhurat_trading_day(d)

    # ------------------------------------------------------------------
    # Range queries
    # ------------------------------------------------------------------

    def get_trading_days(
        self,
        start: str | date | datetime,
        end: str | date | datetime,
        *,
        include_muhurat: bool = False,
    ) -> list[date]:
        """Return trading sessions in [start, end]."""
        start_d = _to_date(start)
        end_d = _to_date(end)

        if start_d > end_d:
            raise ValueError("start must be <= end")

        result: list[date] = []
        current = start_d

        while current <= end_d:
            if self.is_trading_day(current):
                result.append(current)
            elif include_muhurat and self.is_muhurat_trading_day(current):
                result.append(current)

            current += timedelta(days=1)

        return result

    def trading_days_between(
        self,
        start: str | date | datetime,
        end: str | date | datetime,
        *,
        include_muhurat: bool = False,
    ) -> int:
        return len(
            self.get_trading_days(
                start,
                end,
                include_muhurat=include_muhurat,
            )
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def next_trading_day(
        self,
        day: str | date | datetime,
        *,
        include_muhurat: bool = False,
    ) -> date:
        d = _to_date(day) + timedelta(days=1)

        while True:
            if self.is_trading_day(d):
                return d

            if include_muhurat and self.is_muhurat_trading_day(d):
                return d

            d += timedelta(days=1)

    def previous_trading_day(
        self,
        day: str | date | datetime,
        *,
        include_muhurat: bool = False,
    ) -> date:
        d = _to_date(day) - timedelta(days=1)

        while True:
            if self.is_trading_day(d):
                return d

            if include_muhurat and self.is_muhurat_trading_day(d):
                return d

            d -= timedelta(days=1)

    def add_trading_days(
        self,
        day: str | date | datetime,
        n: int,
        *,
        include_muhurat: bool = False,
    ) -> date:
        d = _to_date(day)

        if n == 0:
            if self.is_trading_day(d):
                return d

            if include_muhurat and self.is_muhurat_trading_day(d):
                return d

            return self.next_trading_day(
                d,
                include_muhurat=include_muhurat,
            )

        step = 1 if n > 0 else -1
        remaining = abs(n)

        while remaining:
            d += timedelta(days=step)

            valid = self.is_trading_day(d)

            if include_muhurat:
                valid = valid or self.is_muhurat_trading_day(d)

            if valid:
                remaining -= 1

        return d

    def align_to_trading_day(
        self,
        day: str | date | datetime,
        direction: str = "next",
        *,
        include_muhurat: bool = False,
    ) -> date:
        d = _to_date(day)

        valid = self.is_trading_day(d)

        if include_muhurat:
            valid = valid or self.is_muhurat_trading_day(d)

        if valid:
            return d

        if direction == "next":
            return self.next_trading_day(
                d,
                include_muhurat=include_muhurat,
            )

        if direction == "previous":
            return self.previous_trading_day(
                d,
                include_muhurat=include_muhurat,
            )

        raise ValueError("direction must be 'next' or 'previous'.")

    # ------------------------------------------------------------------
    # Holiday metadata
    # ------------------------------------------------------------------

    def get_holiday(self, day: str | date | datetime) -> Holiday | None:
        return self._holidays.get(_to_date(day))

    def get_holidays(
        self,
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
    ) -> list[Holiday]:
        holidays = sorted(self._holidays.values(), key=lambda x: x.date)

        if start is not None:
            start_d = _to_date(start)
            holidays = [h for h in holidays if h.date >= start_d]

        if end is not None:
            end_d = _to_date(end)
            holidays = [h for h in holidays if h.date <= end_d]

        return holidays

    def add_holiday(
        self,
        day: str | date | datetime,
        name: str = "Custom holiday",
    ) -> None:
        d = _to_date(day)
        self._holidays[d] = Holiday(d, name)

    def remove_holiday(self, day: str | date | datetime) -> None:
        self._holidays.pop(_to_date(day), None)

    @property
    def holidays(self) -> set[date]:
        return set(self._holidays)

    @property
    def muhurat_dates(self) -> dict[date, str]:
        return dict(self._muhurat_dates)

    # ------------------------------------------------------------------
    # JSON persistence
    # ------------------------------------------------------------------

    def to_json(self, path: str | Path) -> None:
        payload = {
            "exchange": "NSE",
            "segment": "Capital Market / Equity Cash",
            "holidays": [
                {
                    "date": h.date.isoformat(),
                    "name": h.name,
                }
                for h in self.get_holidays()
            ],
            "muhurat_trading": [
                {
                    "date": d.isoformat(),
                    "name": name,
                }
                for d, name in sorted(self._muhurat_dates.items())
            ],
        }

        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)

    @classmethod
    def from_json(cls, path: str | Path) -> "TradingCalendar":
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)

        holidays = {}

        for item in payload.get("holidays", []):
            d = _to_date(item["date"])
            holidays[d] = Holiday(d, item.get("name", "NSE holiday"))

        muhurat = {
            _to_date(item["date"]): item.get(
                "name",
                "Diwali Laxmi Pujan",
            )
            for item in payload.get("muhurat_trading", [])
        }

        return cls(
            holidays=holidays,
            muhurat_dates=muhurat,
        )


# ---------------------------------------------------------------------------
# Module-level convenience API
# ---------------------------------------------------------------------------

_default_calendar: TradingCalendar | None = None


def get_calendar() -> TradingCalendar:
    global _default_calendar

    if _default_calendar is None:
        _default_calendar = TradingCalendar()

    return _default_calendar


def is_trading_day(day):
    return get_calendar().is_trading_day(day)


def is_holiday(day):
    return get_calendar().is_holiday(day)


def is_muhurat_trading_day(day):
    return get_calendar().is_muhurat_trading_day(day)


def is_any_trading_session(day):
    return get_calendar().is_any_trading_session(day)


def get_trading_days(start, end, include_muhurat=False):
    return get_calendar().get_trading_days(
        start,
        end,
        include_muhurat=include_muhurat,
    )


def trading_days_between(start, end, include_muhurat=False):
    return get_calendar().trading_days_between(
        start,
        end,
        include_muhurat=include_muhurat,
    )


def next_trading_day(day, include_muhurat=False):
    return get_calendar().next_trading_day(
        day,
        include_muhurat=include_muhurat,
    )


def previous_trading_day(day, include_muhurat=False):
    return get_calendar().previous_trading_day(
        day,
        include_muhurat=include_muhurat,
    )


def add_trading_days(day, n, include_muhurat=False):
    return get_calendar().add_trading_days(
        day,
        n,
        include_muhurat=include_muhurat,
    )


def align_to_trading_day(
    day,
    direction="next",
    include_muhurat=False,
):
    return get_calendar().align_to_trading_day(
        day,
        direction,
        include_muhurat=include_muhurat,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="NSE India equity cash-market trading calendar."
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("is-trading-day")
    p.add_argument("date")

    p = sub.add_parser("next")
    p.add_argument("date")

    p = sub.add_parser("previous")
    p.add_argument("date")

    p = sub.add_parser("add")
    p.add_argument("date")
    p.add_argument("n", type=int)

    p = sub.add_parser("range")
    p.add_argument("start")
    p.add_argument("end")
    p.add_argument("--include-muhurat", action="store_true")

    p = sub.add_parser("align")
    p.add_argument("date")
    p.add_argument(
        "--direction",
        choices=["next", "previous"],
        default="next",
    )
    p.add_argument("--include-muhurat", action="store_true")

    p = sub.add_parser("muhurat")
    p.add_argument("date")

    p = sub.add_parser("holidays")
    p.add_argument("--start")
    p.add_argument("--end")

    p = sub.add_parser("dump")
    p.add_argument("path")

    args = parser.parse_args()
    calendar = get_calendar()

    if args.command == "is-trading-day":
        d = _to_date(args.date)
        print(calendar.is_trading_day(d))

    elif args.command == "next":
        print(calendar.next_trading_day(args.date))

    elif args.command == "previous":
        print(calendar.previous_trading_day(args.date))

    elif args.command == "add":
        print(calendar.add_trading_days(args.date, args.n))

    elif args.command == "range":
        days = calendar.get_trading_days(
            args.start,
            args.end,
            include_muhurat=args.include_muhurat,
        )

        for d in days:
            print(d)

    elif args.command == "align":
        print(
            calendar.align_to_trading_day(
                args.date,
                args.direction,
                include_muhurat=args.include_muhurat,
            )
        )

    elif args.command == "muhurat":
        d = _to_date(args.date)

        if calendar.is_muhurat_trading_day(d):
            print(f"True: {calendar.muhurat_dates[d]}")
        else:
            print("False")

    elif args.command == "holidays":
        for holiday in calendar.get_holidays(
            args.start,
            args.end,
        ):
            print(
                f"{holiday.date}: {holiday.name}"
            )

    elif args.command == "dump":
        calendar.to_json(args.path)
        print(f"Calendar written to {args.path}")


if __name__ == "__main__":
    main()