"""
data/normalization.py
---------------------
Normalization boundary between loaders and validation.

Responsibilities:
    - Clean ticker symbols
    - Validate dates
    - Convert numeric fields to Decimal
    - Convert volume to int
    - Construct OHLCV objects
    - Return per-row normalization errors

This module does NOT:
    - Parse source-specific date formats
    - Remap source-specific column names
    - Perform dataset-level validation
    - Write to Turso
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Sequence

from data.schemas import (
    DataSource,
    OHLCV,
    validate_date,
    validate_ticker,
)


# ============================================================================
# Numeric conversion
# ============================================================================

def parse_flexible_date(value: object, field_name: str) -> Optional[date]:
    """Parse the date formats used by the project's reference-data loaders."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    raise ValueError(
        f"{field_name}={value!r} is not a recognized date format "
        "(expected YYYY-MM-DD or DD-MMM-YYYY)."
    )


def _to_decimal(
    value: object,
    field_name: str,
) -> Decimal:
    """
    Convert a raw numeric value into a finite Decimal.

    Supports:
        Decimal
        int
        float
        str
        strings containing commas, e.g. "1,234.50"

    Rejects:
        bool
        empty strings
        NaN
        Infinity
        invalid numeric strings
    """

    # bool is a subclass of int in Python.
    if isinstance(value, bool):
        raise TypeError(
            f"{field_name} cannot be a boolean."
        )

    if isinstance(value, Decimal):
        result = value

    elif isinstance(value, int):
        result = Decimal(value)

    elif isinstance(value, float):
        result = Decimal(str(value))

    elif isinstance(value, str):
        cleaned = value.strip().replace(",", "")

        if not cleaned:
            raise ValueError(
                f"{field_name} is empty."
            )

        try:
            result = Decimal(cleaned)

        except InvalidOperation as error:
            raise ValueError(
                f"{field_name}={value!r} "
                "is not a valid number."
            ) from error

    else:
        raise TypeError(
            f"{field_name} must be Decimal, int, "
            f"float, or str; got {type(value).__name__}."
        )

    if not result.is_finite():
        raise ValueError(
            f"{field_name} must be finite."
        )

    return result


# Public compatibility wrapper for reference-data loaders.
def to_decimal(value: object, field_name: str) -> Decimal:
    return _to_decimal(value, field_name)


# ============================================================================
# Error type
# ============================================================================

@dataclass(frozen=True)
class RowError:
    """
    Normalization error for one raw row.

    raw_row:
        Original loader output.

    error:
        Human-readable reason.

    This is later converted by ingest.py into rejected_rows.
    """

    raw_row: dict[str, object]
    error: str


# ============================================================================
# Single-row normalization
# ============================================================================

def normalize_ohlcv_row(
    raw_ticker: object,
    trade_date: object,
    open_: object,
    high: object,
    low: object,
    close: object,
    *,
    volume: Optional[object] = None,
    source: DataSource = DataSource.CSV_EXPORT,
    source_file: Optional[str] = None,
) -> OHLCV:
    """
    Normalize one raw record into an OHLCV object.

    OHLCV itself remains responsible for single-row
    market-data consistency checks.
    """

    if not isinstance(raw_ticker, str):
        raise TypeError(
            "ticker must be a string."
        )

    ticker = validate_ticker(raw_ticker)

    if not isinstance(trade_date, date):
        raise TypeError(
            "trade_date must already be a Python date."
        )

    normalized_date = validate_date(
        trade_date
    )

    volume_int: Optional[int] = None

    if volume is not None and volume != "":
        volume_decimal = _to_decimal(
            volume,
            "volume",
        )

        if volume_decimal < 0:
            raise ValueError(
                f"volume={volume!r} "
                "cannot be negative."
            )

        if (
            volume_decimal
            != volume_decimal.to_integral_value()
        ):
            raise ValueError(
                f"volume={volume!r} "
                "must be a whole number."
            )

        volume_int = int(volume_decimal)

    return OHLCV(
        ticker=ticker,
        trade_date=normalized_date,
        open=_to_decimal(open_, "open"),
        high=_to_decimal(high, "high"),
        low=_to_decimal(low, "low"),
        close=_to_decimal(close, "close"),
        volume=volume_int,
        source=source,
        source_file=source_file,
    )


# ============================================================================
# Batch normalization
# ============================================================================

def normalize_ohlcv_rows(
    raw_rows: Sequence[dict[str, object]],
) -> tuple[list[OHLCV], list[RowError]]:
    """
    Normalize a batch of raw loader records.

    One bad row does NOT abort the entire batch.

    Returns:
        (
            valid OHLCV objects,
            normalization errors
        )
    """

    good: list[OHLCV] = []
    bad: list[RowError] = []

    for raw_row in raw_rows:
        try:
            normalized = normalize_ohlcv_row(
                raw_ticker=raw_row["ticker"],
                trade_date=raw_row["trade_date"],
                open_=raw_row["open"],
                high=raw_row["high"],
                low=raw_row["low"],
                close=raw_row["close"],
                volume=raw_row.get("volume"),
                source=raw_row.get(
                    "source",
                    DataSource.CSV_EXPORT,
                ),
                source_file=raw_row.get(
                    "source_file"
                ),
            )

        except KeyError as error:
            bad.append(
                RowError(
                    raw_row=raw_row,
                    error=(
                        "missing required field: "
                        f"{error}"
                    ),
                )
            )

        except (ValueError, TypeError) as error:
            bad.append(
                RowError(
                    raw_row=raw_row,
                    error=str(error),
                )
            )

        else:
            good.append(normalized)

    return good, bad


# ============================================================================
# Compatibility API
# ============================================================================

def normalize_records(
    raw_rows: Sequence[dict[str, object]],
) -> tuple[list[OHLCV], list[dict[str, object]]]:
    """
    Compatibility wrapper used by ingest.py.

    Converts RowError objects into dictionaries so they can
    be directly stored in rejected_rows.

    Returns:
        (
            normalized OHLCV records,
            rejected-row dictionaries
        )
    """

    good, errors = normalize_ohlcv_rows(
        raw_rows
    )

    rejected: list[dict[str, object]] = []

    for error in errors:
        rejected.append(
            {
                "ticker": error.raw_row.get(
                    "ticker"
                ),
                "trade_date": error.raw_row.get(
                    "trade_date"
                ),
                "reason": error.error,
                "raw_payload": error.raw_row,
            }
        )

    return good, rejected


# ============================================================================
# Self-check
# ============================================================================

def self_check() -> None:
    """Run deterministic normalization tests."""

    from datetime import timedelta

    # ------------------------------------------------------------
    # 1. Clean row
    # ------------------------------------------------------------

    row = normalize_ohlcv_row(
        "  nifty bees  ",
        date(2025, 1, 6),
        "100.50",
        "102",
        "99",
        "101.25",
        volume="1,000,000",
    )

    assert row.ticker == "NIFTYBEES"
    assert row.close == Decimal("101.25")
    assert row.volume == 1_000_000

    # ------------------------------------------------------------
    # 2. Thousands separator
    # ------------------------------------------------------------

    row2 = normalize_ohlcv_row(
        "TCS",
        date(2025, 1, 6),
        "1,234.50",
        "1,240",
        "1,230",
        "1,235",
    )

    assert row2.open == Decimal("1234.50")

    # ------------------------------------------------------------
    # 3. Garbage number
    # ------------------------------------------------------------

    try:
        normalize_ohlcv_row(
            "TCS",
            date(2025, 1, 6),
            "N/A",
            "102",
            "99",
            "101",
        )

        raise AssertionError(
            "Invalid price should raise."
        )

    except ValueError as error:
        assert "open" in str(error)

    # ------------------------------------------------------------
    # 4. Future date
    # ------------------------------------------------------------

    tomorrow = (
        date.today()
        + timedelta(days=1)
    )

    try:
        normalize_ohlcv_row(
            "TCS",
            tomorrow,
            "100",
            "102",
            "99",
            "101",
        )

        raise AssertionError(
            "Future date should raise."
        )

    except ValueError:
        pass

    # ------------------------------------------------------------
    # 5. Overlong ticker
    # ------------------------------------------------------------

    try:
        normalize_ohlcv_row(
            "X" * 25,
            date(2025, 1, 6),
            "100",
            "102",
            "99",
            "101",
        )

        raise AssertionError(
            "Overlong ticker should raise."
        )

    except ValueError:
        pass

    # ------------------------------------------------------------
    # 6. Invalid OHLC
    # ------------------------------------------------------------

    try:
        normalize_ohlcv_row(
            "TCS",
            date(2025, 1, 6),
            "100",
            "90",
            "99",
            "101",
        )

        raise AssertionError(
            "Invalid OHLC should raise."
        )

    except ValueError:
        pass

    # ------------------------------------------------------------
    # 7. Batch normalization
    # ------------------------------------------------------------

    raw_rows = [
        {
            "ticker": "TCS",
            "trade_date": date(2025, 1, 6),
            "open": "100",
            "high": "102",
            "low": "99",
            "close": "101",
        },
        {
            "ticker": "INFY",
            "trade_date": date(2025, 1, 6),
            "open": "bad",
            "high": "102",
            "low": "99",
            "close": "101",
        },
        {
            "ticker": "WIPRO",
            "trade_date": date(2025, 1, 6),
            "open": "500",
            "high": "510",
            "low": "495",
            "close": "505",
        },
    ]

    good, bad = normalize_ohlcv_rows(
        raw_rows
    )

    assert len(good) == 2
    assert len(bad) == 1
    assert bad[0].raw_row["ticker"] == "INFY"
    assert "open" in bad[0].error

    # ------------------------------------------------------------
    # 8. Missing field
    # ------------------------------------------------------------

    incomplete = [
        {
            "ticker": "TCS",
            "trade_date": date(2025, 1, 6),
            "open": "100",
            "high": "102",
            "low": "99",
        }
    ]

    good2, bad2 = normalize_ohlcv_rows(
        incomplete
    )

    assert len(good2) == 0
    assert len(bad2) == 1
    assert "close" in bad2[0].error

    # ------------------------------------------------------------
    # 9. NaN / Infinity
    # ------------------------------------------------------------

    for bad_value in (
        float("nan"),
        float("inf"),
        float("-inf"),
    ):
        try:
            normalize_ohlcv_row(
                "TCS",
                date(2025, 1, 6),
                bad_value,
                "102",
                "99",
                "101",
            )

            raise AssertionError(
                f"{bad_value} should raise."
            )

        except ValueError:
            pass

    # ------------------------------------------------------------
    # 10. Decimal NaN / Infinity
    # ------------------------------------------------------------

    for bad_decimal in (
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ):
        try:
            normalize_ohlcv_row(
                "TCS",
                date(2025, 1, 6),
                bad_decimal,
                "102",
                "99",
                "101",
            )

            raise AssertionError(
                f"{bad_decimal} should raise."
            )

        except ValueError:
            pass

    # ------------------------------------------------------------
    # 11. Boolean
    # ------------------------------------------------------------

    try:
        normalize_ohlcv_row(
            "TCS",
            date(2025, 1, 6),
            True,
            "102",
            "99",
            "101",
        )

        raise AssertionError(
            "Boolean price should raise."
        )

    except TypeError as error:
        assert "boolean" in str(error)

    # ------------------------------------------------------------
    # 12. Negative volume
    # ------------------------------------------------------------

    try:
        normalize_ohlcv_row(
            "TCS",
            date(2025, 1, 6),
            "100",
            "102",
            "99",
            "101",
            volume="-500",
        )

        raise AssertionError(
            "Negative volume should raise."
        )

    except ValueError:
        pass

    # ------------------------------------------------------------
    # 13. Fractional volume
    # ------------------------------------------------------------

    try:
        normalize_ohlcv_row(
            "TCS",
            date(2025, 1, 6),
            "100",
            "102",
            "99",
            "101",
            volume=1000.9,
        )

        raise AssertionError(
            "Fractional volume should raise."
        )

    except ValueError:
        pass

    # ------------------------------------------------------------
    # 14. Whole-number float volume
    # ------------------------------------------------------------

    row3 = normalize_ohlcv_row(
        "TCS",
        date(2025, 1, 6),
        "100",
        "102",
        "99",
        "101",
        volume=1000.0,
    )

    assert row3.volume == 1000

    # ------------------------------------------------------------
    # 15. ingest.py compatibility wrapper
    # ------------------------------------------------------------

    normalized, rejected = normalize_records(
        raw_rows
    )

    assert len(normalized) == 2
    assert len(rejected) == 1

    assert rejected[0]["ticker"] == "INFY"
    assert "reason" in rejected[0]
    assert "raw_payload" in rejected[0]

    print("self-check passed")


if __name__ == "__main__":
    self_check()