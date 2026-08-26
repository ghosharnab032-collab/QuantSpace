"""
Data-quality and coverage checks for the NSE market-data layer.

Design goals:
- Keep checks transparent and deterministic.
- Use the NSE trading calendar when checking missing sessions.
- Report suspicious data as WARN rather than silently deleting it.
- Keep this module read-only; it does not modify Turso data.

The anomaly thresholds are intentionally simple warning thresholds:
- Daily absolute return > 20%
- Volume > 10x the median positive volume

These are warnings, not automatic data-rejection rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from statistics import median
from typing import Iterable, Mapping, Sequence

from .trading_calendar import TradingCalendar, get_calendar


class QualityStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class QualityIssue:
    check: str
    status: QualityStatus
    message: str
    ticker: str | None = None
    trade_date: date | None = None


@dataclass(slots=True)
class QualityReport:
    ticker: str | None
    status: QualityStatus = QualityStatus.PASS
    issues: list[QualityIssue] = field(default_factory=list)

    def add(
        self,
        check: str,
        status: QualityStatus,
        message: str,
        *,
        trade_date: date | None = None,
    ) -> None:
        issue = QualityIssue(
            check=check,
            status=status,
            message=message,
            ticker=self.ticker,
            trade_date=trade_date,
        )
        self.issues.append(issue)

        if status == QualityStatus.FAIL:
            self.status = QualityStatus.FAIL
        elif (
            status == QualityStatus.WARN
            and self.status == QualityStatus.PASS
        ):
            self.status = QualityStatus.WARN


def _to_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    if isinstance(value, str):
        return date.fromisoformat(value)

    raise TypeError(
        f"Expected date/datetime/ISO date string, got {type(value).__name__}."
    )


def _number(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value

    if isinstance(value, bool):
        raise TypeError("boolean is not a numeric market value")

    return Decimal(str(value))


def _sort_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    return sorted(
        rows,
        key=lambda row: _to_date(row["trade_date"]),
    )


def check_coverage(
    rows: Sequence[Mapping[str, object]],
    *,
    start: date | str | None = None,
    end: date | str | None = None,
    calendar: TradingCalendar | None = None,
    ticker: str | None = None,
) -> QualityReport:
    """Check expected NSE trading sessions against available price rows."""

    report = QualityReport(ticker=ticker)
    cal = calendar or get_calendar()

    if not rows:
        report.add(
            "coverage",
            QualityStatus.FAIL,
            "No price rows available.",
        )
        return report

    ordered = _sort_rows(rows)
    actual_dates = {_to_date(row["trade_date"]) for row in ordered}

    actual_start = min(actual_dates)
    actual_end = max(actual_dates)

    expected_start = _to_date(start) if start is not None else actual_start
    expected_end = _to_date(end) if end is not None else actual_end

    if expected_start > expected_end:
        raise ValueError("start must be <= end")

    expected_dates = set(
        cal.get_trading_days(expected_start, expected_end)
    )
    missing = sorted(expected_dates - actual_dates)

    if missing:
        report.add(
            "missing_trading_days",
            QualityStatus.WARN,
            f"{len(missing)} expected NSE trading sessions are missing.",
        )
    else:
        report.add(
            "missing_trading_days",
            QualityStatus.PASS,
            "No expected NSE trading sessions are missing.",
        )

    report.add(
        "coverage",
        QualityStatus.PASS,
        (
            f"Coverage {actual_start.isoformat()} to "
            f"{actual_end.isoformat()} with {len(actual_dates)} dates."
        ),
    )

    return report


def check_duplicates(
    rows: Sequence[Mapping[str, object]],
    *,
    ticker: str | None = None,
) -> QualityReport:
    """Check for duplicate ticker + trade_date records."""

    report = QualityReport(ticker=ticker)
    seen: set[tuple[str | None, date]] = set()
    duplicates: list[date] = []

    for row in rows:
        row_ticker = row.get("ticker")
        trade_date = _to_date(row["trade_date"])
        key = (str(row_ticker) if row_ticker is not None else ticker, trade_date)

        if key in seen:
            duplicates.append(trade_date)
        else:
            seen.add(key)

    if duplicates:
        report.add(
            "duplicates",
            QualityStatus.FAIL,
            f"{len(duplicates)} duplicate ticker/date records found.",
        )
    else:
        report.add(
            "duplicates",
            QualityStatus.PASS,
            "No duplicate ticker/date records found.",
        )

    return report


def check_ohlc(
    rows: Sequence[Mapping[str, object]],
    *,
    ticker: str | None = None,
) -> QualityReport:
    """Check required OHLC values and basic OHLC consistency."""

    report = QualityReport(ticker=ticker)
    bad_rows = 0

    required = ("open", "high", "low", "close")

    for row in rows:
        trade_date = _to_date(row["trade_date"])

        try:
            values = {field: _number(row[field]) for field in required}
        except (KeyError, TypeError, ValueError, ArithmeticError):
            bad_rows += 1
            continue

        if any(value <= 0 for value in values.values()):
            bad_rows += 1
            continue

        if not (
            values["high"] >= values["open"]
            and values["high"] >= values["close"]
            and values["low"] <= values["open"]
            and values["low"] <= values["close"]
        ):
            bad_rows += 1
            report.add(
                "ohlc_integrity",
                QualityStatus.FAIL,
                "OHLC relationship is invalid.",
                trade_date=trade_date,
            )

    if bad_rows:
        report.add(
            "missing_or_invalid_ohlc",
            QualityStatus.FAIL,
            f"{bad_rows} rows have missing or invalid OHLC values.",
        )
    else:
        report.add(
            "ohlc_integrity",
            QualityStatus.PASS,
            "All OHLC rows satisfy basic integrity checks.",
        )

    return report


def check_volume(
    rows: Sequence[Mapping[str, object]],
    *,
    ticker: str | None = None,
) -> QualityReport:
    """Check volume values and flag unusually large volume spikes."""

    report = QualityReport(ticker=ticker)

    positive_volumes: list[Decimal] = []
    invalid = 0

    for row in rows:
        volume = row.get("volume")

        if volume is None or volume == "":
            continue

        try:
            value = _number(volume)
        except (TypeError, ValueError, ArithmeticError):
            invalid += 1
            continue

        if value < 0 or value != value.to_integral_value():
            invalid += 1
            continue

        if value > 0:
            positive_volumes.append(value)

    if invalid:
        report.add(
            "volume_integrity",
            QualityStatus.FAIL,
            f"{invalid} rows have invalid volume values.",
        )
    else:
        report.add(
            "volume_integrity",
            QualityStatus.PASS,
            "No invalid volume values found.",
        )

    if positive_volumes:
        baseline = median(positive_volumes)
        if baseline > 0:
            spikes = sum(
                1
                for row in rows
                if row.get("volume") not in (None, "")
                and _number(row["volume"]) > baseline * Decimal("10")
            )

            if spikes:
                report.add(
                    "volume_anomaly",
                    QualityStatus.WARN,
                    f"{spikes} volume observations exceed 10x median volume.",
                )
            else:
                report.add(
                    "volume_anomaly",
                    QualityStatus.PASS,
                    "No volume observations exceed 10x median volume.",
                )

    return report


def check_price_anomalies(
    rows: Sequence[Mapping[str, object]],
    *,
    ticker: str | None = None,
    threshold: Decimal = Decimal("0.20"),
) -> QualityReport:
    """Flag large absolute close-to-close returns as warnings."""

    report = QualityReport(ticker=ticker)
    ordered = _sort_rows(rows)

    previous_close: Decimal | None = None
    anomalies = 0

    for row in ordered:
        trade_date = _to_date(row["trade_date"])

        try:
            close = _number(row["close"])
        except (KeyError, TypeError, ValueError, ArithmeticError):
            previous_close = None
            continue

        if previous_close is not None and previous_close > 0:
            daily_return = abs(close / previous_close - Decimal("1"))

            if daily_return > threshold:
                anomalies += 1
                report.add(
                    "price_anomaly",
                    QualityStatus.WARN,
                    (
                        f"Absolute close-to-close return "
                        f"{daily_return:.2%} exceeds {threshold:.0%}."
                    ),
                    trade_date=trade_date,
                )

        previous_close = close

    if anomalies == 0:
        report.add(
            "price_anomaly",
            QualityStatus.PASS,
            f"No absolute daily returns exceed {threshold:.0%}.",
        )

    return report


def check_universe_consistency(
    price_rows: Sequence[Mapping[str, object]],
    assets: Iterable[Mapping[str, object] | str],
) -> QualityReport:
    """Check that every price ticker exists in the supported asset universe."""

    report = QualityReport(ticker=None)

    asset_tickers: set[str] = set()

    for asset in assets:
        if isinstance(asset, str):
            asset_tickers.add(asset)
        else:
            ticker = asset.get("ticker")
            if ticker:
                asset_tickers.add(str(ticker))

    price_tickers = {
        str(row["ticker"])
        for row in price_rows
        if row.get("ticker")
    }

    orphaned = sorted(price_tickers - asset_tickers)

    if orphaned:
        report.add(
            "universe_consistency",
            QualityStatus.FAIL,
            f"{len(orphaned)} price tickers are missing from assets.",
        )
    else:
        report.add(
            "universe_consistency",
            QualityStatus.PASS,
            "All price tickers exist in the asset universe.",
        )

    return report


def check_price_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    start: date | str | None = None,
    end: date | str | None = None,
    ticker: str | None = None,
    calendar: TradingCalendar | None = None,
) -> QualityReport:
    """Run the core row-level checks and return one combined report."""

    report = QualityReport(ticker=ticker)

    checks = (
        check_coverage(
            rows,
            start=start,
            end=end,
            calendar=calendar,
            ticker=ticker,
        ),
        check_duplicates(rows, ticker=ticker),
        check_ohlc(rows, ticker=ticker),
        check_volume(rows, ticker=ticker),
        check_price_anomalies(rows, ticker=ticker),
    )

    for result in checks:
        for issue in result.issues:
            report.add(
                issue.check,
                issue.status,
                issue.message,
                trade_date=issue.trade_date,
            )

    return report


def print_report(report: QualityReport) -> None:
    """Print a compact human-readable quality report."""

    print("=== DATA QUALITY REPORT ===")
    if report.ticker:
        print(f"Ticker: {report.ticker}")

    for issue in report.issues:
        suffix = (
            f" [{issue.trade_date}]"
            if issue.trade_date is not None
            else ""
        )
        print(
            f"{issue.status.value}: "
            f"{issue.check}: "
            f"{issue.message}{suffix}"
        )

    print(f"\nOverall: {report.status.value}")


def self_check() -> None:
    """Deterministic tests for the data-quality layer."""

    rows = [
        {
            "ticker": "TCS",
            "trade_date": "2026-08-17",
            "open": "100",
            "high": "102",
            "low": "99",
            "close": "101",
            "volume": 1000,
        },
        {
            "ticker": "TCS",
            "trade_date": "2026-08-18",
            "open": "101",
            "high": "103",
            "low": "100",
            "close": "102",
            "volume": 1100,
        },
        {
            "ticker": "TCS",
            "trade_date": "2026-08-19",
            "open": "102",
            "high": "104",
            "low": "101",
            "close": "103",
            "volume": 1200,
        },
    ]

    # 1. Complete coverage for three consecutive NSE sessions.
    coverage = check_coverage(
        rows,
        start="2026-08-17",
        end="2026-08-19",
    )
    assert coverage.status == QualityStatus.PASS
    print("1. Coverage check: OK")

    # 2. Missing trading session is a warning, not a failure.
    missing = check_coverage(
        rows[:1] + rows[2:],
        start="2026-08-17",
        end="2026-08-19",
    )
    assert missing.status == QualityStatus.WARN
    print("2. Missing trading session warning: OK")

    # 3. Duplicate ticker/date fails.
    duplicate = check_duplicates(rows + [rows[0]])
    assert duplicate.status == QualityStatus.FAIL
    print("3. Duplicate detection: OK")

    # 4. Valid OHLC passes.
    ohlc = check_ohlc(rows)
    assert ohlc.status == QualityStatus.PASS
    print("4. OHLC integrity: OK")

    # 5. Invalid OHLC fails.
    bad_ohlc = dict(rows[0])
    bad_ohlc["high"] = "90"
    ohlc_fail = check_ohlc([bad_ohlc])
    assert ohlc_fail.status == QualityStatus.FAIL
    print("5. Invalid OHLC detection: OK")

    # 6. Large return warns rather than failing.
    jump = dict(rows[1])
    jump["close"] = "130"
    anomaly = check_price_anomalies([rows[0], jump])
    assert anomaly.status == QualityStatus.WARN
    print("6. Price anomaly warning: OK")

    # 7. Invalid volume fails.
    bad_volume = dict(rows[0])
    bad_volume["volume"] = -1
    volume_fail = check_volume([bad_volume])
    assert volume_fail.status == QualityStatus.FAIL
    print("7. Invalid volume detection: OK")

    # 8. Universe consistency.
    universe = check_universe_consistency(
        rows,
        [{"ticker": "TCS"}, {"ticker": "INFY"}],
    )
    assert universe.status == QualityStatus.PASS
    print("8. Universe consistency: OK")

    # 9. Orphaned ticker fails.
    orphan = dict(rows[0])
    orphan["ticker"] = "UNKNOWN"
    universe_fail = check_universe_consistency(
        [orphan],
        [{"ticker": "TCS"}],
    )
    assert universe_fail.status == QualityStatus.FAIL
    print("9. Orphan ticker detection: OK")

    # 10. Combined report.
    combined = check_price_rows(
        rows,
        start="2026-08-17",
        end="2026-08-19",
        ticker="TCS",
    )
    assert combined.status == QualityStatus.PASS
    print("10. Combined quality report: OK")

    print("\nself-check passed")


if __name__ == "__main__":
    self_check()