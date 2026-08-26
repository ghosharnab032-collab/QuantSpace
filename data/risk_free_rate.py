"""Risk-free-rate time series: store, and query the applicable rate for
a given valuation date.

Scope, deliberately minimal — a single benchmark rate series (e.g. 91-day
T-bill), not a multi-tenor yield curve. "date -> rate" was the literal
ask; a tenor/curve system would be a real, separate feature to build
later if actually needed, not something to half-build speculatively now.

Lookup convention: "the rate as of date D" means the most recent
published rate ON OR BEFORE D — standard forward-fill behavior for a
macro time series that isn't published every single calendar day. No
interpolation between known dates; that's a different, unrequested level
of precision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, Sequence

from .normalization import RowError, parse_flexible_date, to_decimal
from .schemas import DataSource


@dataclass(frozen=True, slots=True)
class RiskFreeRate:
    rate_date: date
    rate: Decimal
    source: DataSource = DataSource.RBI

    def __post_init__(self) -> None:
        if not self.rate.is_finite():
            raise ValueError(f"rate must be finite, got {self.rate}.")
        # Deliberately NOT rejecting negative rates — real markets have
        # had negative sovereign yields (Japan, parts of Europe), even
        # though it'd be unusual for India historically. Only finiteness
        # is actually guaranteed by definition.


def rate_as_of(rates: Sequence[RiskFreeRate], valuation_date: date) -> RiskFreeRate:
    """The applicable rate for valuation_date: the most recent rate at or
    before that date. Raises if none exists rather than silently falling
    back to some default constant — same fail-loud convention as the
    rest of this project."""
    candidates = [r for r in rates if r.rate_date <= valuation_date]
    if not candidates:
        raise ValueError(
            f"No risk-free rate available on or before {valuation_date}. "
            f"Earliest available: {min((r.rate_date for r in rates), default=None)}."
        )
    return max(candidates, key=lambda r: r.rate_date)


def load_risk_free_rate_csv(raw_rows: list[dict[str, object]]) -> tuple[list[RiskFreeRate], list[RowError]]:
    """Batch load, per-row failure collection — same pattern as
    normalize_ohlcv_rows/normalize_asset_rows, not reinvented a third
    time. Also detects duplicate dates: identical redundant rows are
    silently deduplicated (not a real problem), but CONFLICTING rates
    for the same date are rejected as ambiguous — same philosophy as
    validation.py's duplicate-date handling for prices."""
    parsed: list[RiskFreeRate] = []
    bad: list[RowError] = []

    for raw_row in raw_rows:
        try:
            rate_date = parse_flexible_date(raw_row["rate_date"], "rate_date")
            if rate_date is None:
                raise ValueError("rate_date is required and cannot be empty.")
            rate_value = to_decimal(raw_row["rate"], "rate")
            source_raw = raw_row.get("source")
            source = DataSource(source_raw) if source_raw else DataSource.RBI
            parsed.append(RiskFreeRate(rate_date=rate_date, rate=rate_value, source=source))
        except KeyError as exc:
            bad.append(RowError(raw_row, f"missing required field: {exc}"))
        except (ValueError, TypeError) as exc:
            bad.append(RowError(raw_row, str(exc)))

    by_date: dict[date, list[RiskFreeRate]] = {}
    for r in parsed:
        by_date.setdefault(r.rate_date, []).append(r)

    good: list[RiskFreeRate] = []
    for rate_date, group in by_date.items():
        distinct_rates = {r.rate for r in group}
        if len(distinct_rates) > 1:
            bad.append(RowError(
                {"rate_date": rate_date.isoformat(), "conflicting_rates": [str(v) for v in distinct_rates]},
                f"{len(distinct_rates)} conflicting rate values for {rate_date} — which is correct?",
            ))
            continue
        good.append(group[0])  # identical duplicates collapse to one, harmlessly

    return good, bad


UPSERT_SQL = """
INSERT INTO risk_free_rates (rate_date, rate, source, recorded_at)
VALUES (?, ?, ?, ?)
ON CONFLICT(rate_date) DO UPDATE SET
    rate = excluded.rate,
    source = excluded.source,
    recorded_at = excluded.recorded_at
"""


def self_check() -> None:
    from datetime import datetime, timezone

    # 1. HAND-VERIFIED: "as of" a date with no exact rate returns the
    #    most recent PRIOR rate (forward-fill), not an exact-match miss.
    rates = [
        RiskFreeRate(date(2025, 1, 1), Decimal("6.5")),
        RiskFreeRate(date(2025, 2, 1), Decimal("6.7")),
        RiskFreeRate(date(2025, 3, 1), Decimal("6.8")),
    ]
    # Jan 15 has no exact rate -> should return Jan 1's rate (6.5), not Feb's.
    r = rate_as_of(rates, date(2025, 1, 15))
    assert r.rate == Decimal("6.5"), r.rate
    print("1. Forward-fill to most recent prior rate: OK")

    # 2. Exact match on a known rate date returns that exact rate.
    r2 = rate_as_of(rates, date(2025, 2, 1))
    assert r2.rate == Decimal("6.7")
    print("2. Exact-date match: OK")

    # 3. A date on/after the LATEST rate returns the latest rate (still
    #    forward-fill, not an error just because it's "in the future"
    #    relative to the data — that's a legitimate valuation date).
    r3 = rate_as_of(rates, date(2025, 6, 1))
    assert r3.rate == Decimal("6.8")
    print("3. Date after latest rate uses latest available: OK")

    # 4. A date BEFORE any known rate raises, rather than silently
    #    returning nothing usable or a wrong default.
    try:
        rate_as_of(rates, date(2024, 1, 1))
        raise AssertionError("date before all known rates should raise")
    except ValueError as e:
        assert "2024-01-01" in str(e)
    print("4. Date before all known data raises clearly: OK")

    # 5. Empty rates list raises too.
    try:
        rate_as_of([], date(2025, 1, 1))
        raise AssertionError("empty rate series should raise")
    except ValueError:
        pass
    print("5. Empty rate series raises: OK")

    # 6. CSV batch loading: valid rows parse correctly.
    raw = [
        {"rate_date": "2025-01-01", "rate": "6.5"},
        {"rate_date": "01-Feb-2025", "rate": "6.7", "source": "rbi"},
    ]
    good, bad = load_risk_free_rate_csv(raw)
    assert len(good) == 2 and len(bad) == 0
    assert good[0].rate_date == date(2025, 1, 1)
    assert good[1].rate_date == date(2025, 2, 1)  # DD-MMM-YYYY parsed correctly
    print("6. CSV batch load, mixed date formats: OK")

    # 7. Bad rate value collected as a failure, doesn't abort the batch.
    raw2 = [
        {"rate_date": "2025-01-01", "rate": "6.5"},
        {"rate_date": "2025-01-02", "rate": "not-a-number"},
    ]
    good2, bad2 = load_risk_free_rate_csv(raw2)
    assert len(good2) == 1 and len(bad2) == 1
    print("7. Bad rate value rejected, rest of batch still loads: OK")

    # 8. Identical duplicate rows for the same date collapse harmlessly.
    raw3 = [
        {"rate_date": "2025-01-01", "rate": "6.5"},
        {"rate_date": "2025-01-01", "rate": "6.5"},  # redundant, not conflicting
    ]
    good3, bad3 = load_risk_free_rate_csv(raw3)
    assert len(good3) == 1 and len(bad3) == 0
    print("8. Identical duplicate rows collapse without error: OK")

    # 9. CONFLICTING rates for the same date are rejected as ambiguous —
    #    not silently resolved by picking whichever came last.
    raw4 = [
        {"rate_date": "2025-01-01", "rate": "6.5"},
        {"rate_date": "2025-01-01", "rate": "6.9"},  # genuinely different, same date
    ]
    good4, bad4 = load_risk_free_rate_csv(raw4)
    assert len(good4) == 0 and len(bad4) == 1
    assert "conflicting" in bad4[0].error.lower()
    print("9. Conflicting same-date rates rejected as ambiguous: OK")

    # 10. NaN/Infinity rate rejected (reuses to_decimal's existing guard —
    #     not re-implemented here).
    raw5 = [{"rate_date": "2025-01-01", "rate": "nan"}]
    good5, bad5 = load_risk_free_rate_csv(raw5)
    assert len(good5) == 0 and len(bad5) == 1
    print("10. Non-finite rate rejected (via shared to_decimal guard): OK")


if __name__ == "__main__":
    self_check()
    print("\nself-check passed")