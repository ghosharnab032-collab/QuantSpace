"""
Dividend-yield time-series data layer.

Lookup convention:
    latest observation on or before the valuation date.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Sequence

from database.connections import get_connection


@dataclass(frozen=True, slots=True)
class DividendYield:
    ticker: str
    effective_date: date
    dividend_yield: float
    source: str = "manual"
    recorded_at: str = ""

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("ticker cannot be empty")

        if not math.isfinite(self.dividend_yield):
            raise ValueError("dividend_yield must be finite")

        if self.dividend_yield < 0:
            raise ValueError("dividend_yield cannot be negative")


@dataclass(frozen=True, slots=True)
class RowError:
    raw: dict[str, Any]
    error: str


def _parse_date(value: object) -> date | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    for fmt in (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%Y%m%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    return None


def _normalize_ticker(value: object) -> str:
    if value is None:
        raise ValueError("ticker is required")

    ticker = str(value).strip().upper()

    if not ticker:
        raise ValueError("ticker cannot be empty")

    return ticker


def _parse_yield(value: object) -> float:
    if value is None:
        raise ValueError("dividend_yield is required")

    try:
        result = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"invalid dividend_yield: {value!r}"
        ) from exc

    if not math.isfinite(result):
        raise ValueError("dividend_yield must be finite")

    return result


def load_dividend_yield_csv(
    raw_rows: list[dict[str, object]],
) -> tuple[list[DividendYield], list[RowError]]:
    parsed: list[DividendYield] = []
    errors: list[RowError] = []

    for raw in raw_rows:
        try:
            ticker = _normalize_ticker(raw["ticker"])

            effective_date = _parse_date(
                raw["effective_date"]
            )

            if effective_date is None:
                raise ValueError(
                    "effective_date is required and must be valid"
                )

            dividend_yield = _parse_yield(
                raw["dividend_yield"]
            )

            if dividend_yield < 0:
                raise ValueError(
                    "dividend_yield cannot be negative"
                )

            source = (
                str(raw.get("source") or "manual")
                .strip()
                or "manual"
            )

            parsed.append(
                DividendYield(
                    ticker=ticker,
                    effective_date=effective_date,
                    dividend_yield=dividend_yield,
                    source=source,
                    recorded_at=datetime.now(
                        timezone.utc
                    ).isoformat(),
                )
            )

        except KeyError as exc:
            errors.append(
                RowError(
                    raw,
                    f"missing required field: {exc}",
                )
            )

        except (TypeError, ValueError) as exc:
            errors.append(
                RowError(raw, str(exc))
            )

    # Unique key:
    # (ticker, effective_date)
    grouped: dict[
        tuple[str, date],
        list[DividendYield],
    ] = {}

    for record in parsed:
        key = (
            record.ticker,
            record.effective_date,
        )

        grouped.setdefault(key, []).append(record)

    good: list[DividendYield] = []

    for (ticker, effective_date), group in grouped.items():
        distinct = {
            record.dividend_yield
            for record in group
        }

        if len(distinct) > 1:
            errors.append(
                RowError(
                    {
                        "ticker": ticker,
                        "effective_date":
                            effective_date.isoformat(),
                        "conflicting_yields":
                            sorted(distinct),
                    },
                    "conflicting dividend_yield values "
                    "for the same ticker/date",
                )
            )
            continue

        # Identical duplicates collapse.
        good.append(group[0])

    return good, errors


# ============================================================================
# DATABASE
# ============================================================================

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dividend_yields (
    ticker TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    dividend_yield REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    recorded_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (ticker, effective_date)
)
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_dividend_yields_ticker_date
ON dividend_yields(ticker, effective_date)
"""

UPSERT_SQL = """
INSERT INTO dividend_yields (
    ticker,
    effective_date,
    dividend_yield,
    source,
    recorded_at
)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(ticker, effective_date) DO UPDATE SET
    dividend_yield = excluded.dividend_yield,
    source = excluded.source,
    recorded_at = excluded.recorded_at
"""


def ensure_schema(conn: Any) -> None:
    conn.execute(CREATE_TABLE_SQL)
    conn.execute(CREATE_INDEX_SQL)
    conn.commit()


def upsert_dividend_yields(
    conn: Any,
    records: Sequence[DividendYield],
) -> int:
    if not records:
        return 0

    payload = [
        (
            record.ticker,
            record.effective_date.isoformat(),
            record.dividend_yield,
            record.source,
            record.recorded_at
            or datetime.now(timezone.utc).isoformat(),
        )
        for record in records
    ]

    result = conn.executemany(
        UPSERT_SQL,
        payload,
    )

    if hasattr(result, "rows_affected"):
        return int(result.rows_affected)

    if hasattr(result, "rowcount"):
        return int(result.rowcount)

    return len(records)


# ============================================================================
# QUERIES
# ============================================================================

def _as_date(
    value: date | datetime | str,
) -> date:
    parsed = _parse_date(value)

    if parsed is None:
        raise ValueError(
            f"invalid date: {value!r}"
        )

    return parsed


def _fetch_rows(result: Any) -> list[Any]:
    if hasattr(result, "rows"):
        return list(result.rows)

    if hasattr(result, "fetchall"):
        return list(result.fetchall())

    return list(result)


def get_dividend_yield(
    conn: Any,
    ticker: str,
    valuation_date: date | datetime | str,
) -> DividendYield | None:
    """
    Return the most recent observation on or before
    valuation_date.
    """

    normalized_ticker = _normalize_ticker(ticker)
    target_date = _as_date(valuation_date)

    result = conn.execute(
        """
        SELECT
            ticker,
            effective_date,
            dividend_yield,
            source,
            recorded_at
        FROM dividend_yields
        WHERE ticker = ?
          AND effective_date <= ?
        ORDER BY effective_date DESC
        LIMIT 1
        """,
        (
            normalized_ticker,
            target_date.isoformat(),
        ),
    )

    rows = _fetch_rows(result)

    if not rows:
        return None

    row = rows[0]

    return DividendYield(
        ticker=str(row[0]),
        effective_date=_as_date(str(row[1])),
        dividend_yield=float(row[2]),
        source=str(row[3]),
        recorded_at=str(row[4]),
    )


def get_dividend_yields(
    conn: Any,
    tickers: Sequence[str],
    valuation_date: date | datetime | str,
) -> dict[str, DividendYield | None]:
    target_date = _as_date(valuation_date)

    return {
        _normalize_ticker(ticker):
            get_dividend_yield(
                conn,
                ticker,
                target_date,
            )
        for ticker in tickers
    }


def get_dividend_yield_history(
    conn: Any,
    ticker: str,
    start: date | datetime | str,
    end: date | datetime | str,
) -> list[DividendYield]:

    normalized_ticker = _normalize_ticker(ticker)

    start_date = _as_date(start)
    end_date = _as_date(end)

    if start_date > end_date:
        raise ValueError("start must be <= end")

    result = conn.execute(
        """
        SELECT
            ticker,
            effective_date,
            dividend_yield,
            source,
            recorded_at
        FROM dividend_yields
        WHERE ticker = ?
          AND effective_date >= ?
          AND effective_date <= ?
        ORDER BY effective_date
        """,
        (
            normalized_ticker,
            start_date.isoformat(),
            end_date.isoformat(),
        ),
    )

    return [
        DividendYield(
            ticker=str(row[0]),
            effective_date=_as_date(
                str(row[1])
            ),
            dividend_yield=float(row[2]),
            source=str(row[3]),
            recorded_at=str(row[4]),
        )
        for row in _fetch_rows(result)
    ]


# ============================================================================
# DATA QUALITY
# ============================================================================

def run_data_quality_checks(
    conn: Any,
    tickers: Sequence[str] | None = None,
) -> list[dict[str, Any]]:

    filters: list[str] = []
    params: list[str] = []

    if tickers:
        normalized = [
            _normalize_ticker(ticker)
            for ticker in tickers
        ]

        placeholders = ", ".join(
            "?" for _ in normalized
        )

        filters.append(
            f"ticker IN ({placeholders})"
        )

        params.extend(normalized)

    where_clause = (
        "WHERE " + " AND ".join(filters)
        if filters
        else ""
    )

    result = conn.execute(
        f"""
        SELECT
            ticker,
            effective_date,
            dividend_yield
        FROM dividend_yields
        {where_clause}
        ORDER BY ticker, effective_date
        """,
        tuple(params),
    )

    warnings: list[dict[str, Any]] = []
    previous: dict[str, float] = {}

    for row in _fetch_rows(result):
        ticker = str(row[0]).upper()
        effective_date = str(row[1])
        value = float(row[2])

        if (
            not math.isfinite(value)
            or value < 0
            or value > 50
        ):
            warnings.append(
                {
                    "ticker": ticker,
                    "effective_date": effective_date,
                    "issue":
                        "invalid_or_suspicious_yield",
                    "value": value,
                }
            )

        if ticker in previous:
            change = abs(
                value - previous[ticker]
            )

            if change > 10:
                warnings.append(
                    {
                        "ticker": ticker,
                        "effective_date": effective_date,
                        "issue": "large_yield_change",
                        "value": value,
                        "previous":
                            previous[ticker],
                        "change": change,
                    }
                )

        previous[ticker] = value

    return warnings


# ============================================================================
# SELF CHECK
# ============================================================================

def self_check() -> None:

    good, bad = load_dividend_yield_csv(
        [
            {
                "ticker": " tcs ",
                "effective_date":
                    "2025-01-01",
                "dividend_yield": "1.2",
            }
        ]
    )

    assert len(good) == 1
    assert not bad
    assert good[0].ticker == "TCS"
    print("1. Normalization: OK")

    good, bad = load_dividend_yield_csv(
        [
            {
                "ticker": "INFY",
                "effective_date":
                    "01-Feb-2025",
                "dividend_yield": "2.8",
            }
        ]
    )

    assert len(good) == 1
    assert not bad
    print("2. Date parsing: OK")

    good, bad = load_dividend_yield_csv(
        [
            {
                "ticker": "TCS",
                "effective_date":
                    "2025-01-01",
                "dividend_yield": "-1",
            }
        ]
    )

    assert not good
    assert len(bad) == 1
    print("3. Negative yield rejected: OK")

    good, bad = load_dividend_yield_csv(
        [
            {
                "ticker": "TCS",
                "effective_date":
                    "2025-01-01",
                "dividend_yield": "1.2",
            },
            {
                "ticker": "TCS",
                "effective_date":
                    "2025-01-01",
                "dividend_yield": "1.9",
            },
        ]
    )

    assert not good
    assert len(bad) == 1
    print("4. Conflicting duplicate rejected: OK")

    good, bad = load_dividend_yield_csv(
        [
            {
                "ticker": "TCS",
                "effective_date":
                    "2025-01-01",
                "dividend_yield": "1.2",
            },
            {
                "ticker": "TCS",
                "effective_date":
                    "2025-01-01",
                "dividend_yield": "1.2",
            },
        ]
    )

    assert len(good) == 1
    assert not bad
    print("5. Identical duplicate collapsed: OK")

    good, bad = load_dividend_yield_csv(
        [
            {
                "ticker": "TCS",
                "effective_date":
                    "2025-01-01",
                "dividend_yield": "1.2",
            },
            {
                "ticker": "INFY",
                "effective_date":
                    "2025-01-01",
                "dividend_yield": "2.8",
            },
        ]
    )

    assert len(good) == 2
    assert not bad
    print("6. Different tickers same date: OK")

    try:
        get_dividend_yield_history(
            object(),
            "TCS",
            "2025-02-01",
            "2025-01-01",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "reversed date range should raise"
        )

    print("7. Invalid date range rejected: OK")

    print("\nself-check passed")


if __name__ == "__main__":
    self_check()