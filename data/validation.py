"""Cross-row validation for the quant data pipeline.

Runs AFTER normalization (see the architecture diagram) — by this point
tickers/dates/columns are already clean, and single-row checks (positive
prices, OHLC consistency) have already been enforced by `OHLCV.__post_init__`
in schemas.py. This module does NOT re-check those; it only checks things
that need context across multiple rows for the same ticker:

    - duplicate trade dates
    - missing-date gaps (approximate: weekday-only, no holiday calendar)
    - suspicious single-day returns, checked against corporate_actions
      BEFORE being flagged, so a real split/bonus doesn't get rejected
      as bad data — but only for action types that actually move price
      mechanically, and only when the observed move roughly matches what
      the action's ratio predicts (see RATIO CONVENTION below)

Writing PASS/FAIL rows to Turso vs rejected_rows is the orchestrator's job,
not this module's — this module only produces ValidationReport objects.

RATIO CONVENTION (must match whatever writes CorporateAction.ratio):
    SPLIT : ratio = new shares per old share (a 1-for-2 split -> ratio=2).
            expected raw-price factor = 1 / ratio.
    BONUS : ratio = bonus shares issued per share already held
            (a "1:1 bonus" -> ratio=1, holder ends up with 2x shares).
            expected raw-price factor = 1 / (1 + ratio).
    RIGHTS: NOT quantitatively verified here. The price impact of a rights
            issue depends on the subscription price and take-up rate, not
            just the ratio, and that data isn't in this schema yet. A
            RIGHTS action can match by type/date but the PASS message says
            so explicitly rather than implying the magnitude was checked.
    DIVIDEND, MERGER, DEMERGER: never auto-explain a large single-day
            return here. Dividends cause a modest ex-date drop roughly
            equal to the dividend amount, not the kind of move this
            threshold is checking for; merger/demerger aren't verifiable
            yet since schemas.py has no target-ticker/swap-ratio field
            for them (a known, separate gap — see schemas.py review notes).
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Sequence

from data.schemas import (
    CorporateAction,
    CorporateActionType,
    OHLCV,
    ValidationReport,
    ValidationStatus,
)

DEFAULT_SUSPICIOUS_RETURN_THRESHOLD = 0.20
DEFAULT_MAX_GAP_BUSINESS_DAYS = 4
CORPORATE_ACTION_WINDOW_DAYS = 3

# Only these action types mechanically move the raw price enough to
# auto-explain a large single-day return. Dividends, mergers, and
# demergers are deliberately excluded — see module docstring.
PRICE_MOVING_ACTION_TYPES = {
    CorporateActionType.SPLIT,
    CorporateActionType.BONUS,
    CorporateActionType.RIGHTS,
}

# How close the OBSERVED price factor must be to the factor PREDICTED by
# the action's ratio, as a fraction (0.15 = within 15%). Not exact, since
# ex-date timing and same-day trading noise both add slack.
RATIO_MATCH_TOLERANCE = 0.15


def _business_days_between(earlier: date, later: date) -> int:
    count = 0
    current = earlier + timedelta(days=1)
    while current < later:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def _expected_price_factor(action: CorporateAction) -> Optional[float]:
    """The raw-price multiplier this action predicts, or None if not
    quantitatively verifiable from ratio alone (see RATIO CONVENTION)."""
    if action.action_type is CorporateActionType.SPLIT:
        return 1.0 / float(action.ratio)
    if action.action_type is CorporateActionType.BONUS:
        return 1.0 / (1.0 + float(action.ratio))
    return None  # RIGHTS: type-matched only, not verified quantitatively.


def _find_corporate_action(
    ticker: str,
    trade_date: date,
    actions: Sequence[tuple[int, CorporateAction]],
) -> Optional[tuple[int, CorporateAction]]:
    window = timedelta(days=CORPORATE_ACTION_WINDOW_DAYS)
    candidates = [
        (action_id, action)
        for action_id, action in actions
        if action.ticker == ticker
        and action.action_type in PRICE_MOVING_ACTION_TYPES
        and abs(action.ex_date - trade_date) <= window
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda pair: abs(pair[1].ex_date - trade_date))


def validate_ohlcv_series(
    rows: Sequence[OHLCV],
    *,
    run_id: str,
    corporate_actions: Optional[Sequence[tuple[int, CorporateAction]]] = None,
    suspicious_return_threshold: float = DEFAULT_SUSPICIOUS_RETURN_THRESHOLD,
    max_gap_business_days: int = DEFAULT_MAX_GAP_BUSINESS_DAYS,
) -> list[ValidationReport]:
    """Validate a same-ticker series of OHLCV rows.

    `corporate_actions` takes (id, CorporateAction) pairs, not bare
    CorporateAction objects — CorporateAction itself has no persisted ID
    pre-insert (it's a domain object, not a DB row), so the caller must
    supply whatever ID Turso actually assigned. Using Python's id()
    (object memory address) here would be a real bug: it's not stable
    across runs and can't be used to reference the record later.
    """
    if not rows:
        return []

    tickers = {row.ticker for row in rows}
    if len(tickers) > 1:
        raise ValueError(
            f"validate_ohlcv_series expects one ticker, got {sorted(tickers)}. "
            "Call it once per ticker."
        )

    if not math.isfinite(suspicious_return_threshold) or suspicious_return_threshold <= 0:
        raise ValueError("suspicious_return_threshold must be a finite positive number.")
    if max_gap_business_days < 0:
        raise ValueError("max_gap_business_days cannot be negative.")

    ticker = rows[0].ticker
    actions = corporate_actions or []

    ordered = sorted(rows, key=lambda r: r.trade_date)
    reports: list[ValidationReport] = []

    if list(rows) != ordered:
        reports.append(
            ValidationReport(
                run_id=run_id,
                ticker=ticker,
                trade_date=ordered[0].trade_date,
                status=ValidationStatus.WARN,
                message="input rows were not in trade_date order; sorted before validation.",
            )
        )

    seen_dates: dict[date, int] = {}
    for row in ordered:
        seen_dates[row.trade_date] = seen_dates.get(row.trade_date, 0) + 1

    # `previous` only ever advances to a row we've confirmed is NOT a
    # duplicate. A duplicate's price is ambiguous by definition — using
    # it as the anchor for the next row's return calculation would let
    # one bad/duplicate row fabricate a false "suspicious return" on a
    # completely unrelated later row. (Confirmed with a live reproduction
    # before this fix: a glitchy duplicate turned a real +1% day into a
    # reported +152% one.)
    previous: Optional[OHLCV] = None

    for row in ordered:
        if seen_dates[row.trade_date] > 1:
            reports.append(
                ValidationReport(
                    run_id=run_id,
                    ticker=ticker,
                    trade_date=row.trade_date,
                    status=ValidationStatus.FAIL,
                    message=f"duplicate trade_date ({seen_dates[row.trade_date]} rows).",
                )
            )
            continue  # previous intentionally NOT advanced here.

        if previous is not None:
            gap = _business_days_between(previous.trade_date, row.trade_date)
            if gap > max_gap_business_days:
                reports.append(
                    ValidationReport(
                        run_id=run_id,
                        ticker=ticker,
                        trade_date=row.trade_date,
                        status=ValidationStatus.WARN,
                        message=(
                            f"{gap} business day(s) since previous unique row "
                            f"({previous.trade_date}) — may be a missing-data "
                            "gap, or an unmodeled holiday."
                        ),
                    )
                )

            observed_factor = float(row.close / previous.close)
            day_return = observed_factor - 1.0

            if abs(day_return) > suspicious_return_threshold:
                match = _find_corporate_action(ticker, row.trade_date, actions)

                if match is None:
                    reports.append(
                        ValidationReport(
                            run_id=run_id,
                            ticker=ticker,
                            trade_date=row.trade_date,
                            status=ValidationStatus.FAIL,
                            message=(
                                f"{day_return:+.1%} move exceeds "
                                f"{suspicious_return_threshold:.0%} threshold "
                                "with no matching price-moving corporate action."
                            ),
                        )
                    )
                else:
                    action_id, action = match
                    expected_factor = _expected_price_factor(action)

                    if expected_factor is None:
                        reports.append(
                            ValidationReport(
                                run_id=run_id,
                                ticker=ticker,
                                trade_date=row.trade_date,
                                status=ValidationStatus.WARN,
                                message=(
                                    f"{day_return:+.1%} move coincides with a "
                                    f"{action.action_type.value} on {action.ex_date}, "
                                    "but the expected magnitude isn't verified for "
                                    "this action type — review manually."
                                ),
                                matching_corporate_action_id=action_id,
                            )
                        )
                    elif abs(observed_factor - expected_factor) / expected_factor <= RATIO_MATCH_TOLERANCE:
                        reports.append(
                            ValidationReport(
                                run_id=run_id,
                                ticker=ticker,
                                trade_date=row.trade_date,
                                status=ValidationStatus.PASS,
                                message=(
                                    f"{day_return:+.1%} move matches "
                                    f"{action.action_type.value} on {action.ex_date} "
                                    f"(expected factor {expected_factor:.3f}, "
                                    f"observed {observed_factor:.3f})."
                                ),
                                matching_corporate_action_id=action_id,
                            )
                        )
                    else:
                        reports.append(
                            ValidationReport(
                                run_id=run_id,
                                ticker=ticker,
                                trade_date=row.trade_date,
                                status=ValidationStatus.FAIL,
                                message=(
                                    f"{day_return:+.1%} move near a "
                                    f"{action.action_type.value} on {action.ex_date}, "
                                    f"but observed factor {observed_factor:.3f} doesn't "
                                    f"match the ratio-predicted factor {expected_factor:.3f} "
                                    f"(tolerance {RATIO_MATCH_TOLERANCE:.0%})."
                                ),
                                matching_corporate_action_id=action_id,
                            )
                        )

        previous = row

    return reports


def rejected_keys(reports: Sequence[ValidationReport]) -> set[tuple[str, date]]:
    """(ticker, trade_date) pairs that failed validation — the
    orchestrator's cue to route those specific rows to rejected_rows
    instead of Turso. Keyed by ticker as well as date, since a single
    run may validate multiple securities and dates alone would collapse
    unrelated failures across tickers into one entry."""
    return {(r.ticker, r.trade_date) for r in reports if r.status is ValidationStatus.FAIL}


def self_check() -> None:
    def make_row(ticker: str, d: date, close: str) -> OHLCV:
        c = Decimal(close)
        return OHLCV(ticker, d, c, c, c, c)

    clean = [
        make_row("TCS", date(2025, 1, 6), "100"),
        make_row("TCS", date(2025, 1, 7), "101"),
        make_row("TCS", date(2025, 1, 8), "100.5"),
    ]
    assert validate_ohlcv_series(clean, run_id="r1") == []

    dup = [
        make_row("TCS", date(2025, 1, 6), "100"),
        make_row("TCS", date(2025, 1, 6), "100"),
    ]
    reports = validate_ohlcv_series(dup, run_id="r2")
    assert len(reports) == 2 and all(r.status is ValidationStatus.FAIL for r in reports)

    poison_test = [
        make_row("TCS", date(2025, 1, 6), "100"),
        make_row("TCS", date(2025, 1, 7), "100"),
        make_row("TCS", date(2025, 1, 7), "40"),
        make_row("TCS", date(2025, 1, 8), "101"),
    ]
    reports = validate_ohlcv_series(poison_test, run_id="r3")
    jan8 = [r for r in reports if r.trade_date == date(2025, 1, 8)]
    assert jan8 == [], f"duplicate poisoned the anchor: got {jan8}"

    gapped = [
        make_row("TCS", date(2025, 1, 6), "100"),
        make_row("TCS", date(2025, 1, 20), "101"),
    ]
    reports = validate_ohlcv_series(gapped, run_id="r4")
    assert len(reports) == 1 and reports[0].status is ValidationStatus.WARN

    jump = [
        make_row("TCS", date(2025, 1, 6), "100"),
        make_row("TCS", date(2025, 1, 7), "150"),
    ]
    reports = validate_ohlcv_series(jump, run_id="r5")
    assert len(reports) == 1 and reports[0].status is ValidationStatus.FAIL

    dividend = (1, CorporateAction("TCS", date(2025, 1, 7), CorporateActionType.DIVIDEND, value=Decimal("5")))
    reports = validate_ohlcv_series(jump, run_id="r6", corporate_actions=[dividend])
    assert len(reports) == 1 and reports[0].status is ValidationStatus.FAIL, (
        "a dividend must not auto-explain an unrelated large price jump"
    )

    half = [
        make_row("TCS", date(2025, 1, 6), "100"),
        make_row("TCS", date(2025, 1, 7), "50"),
    ]
    split = (77, CorporateAction("TCS", date(2025, 1, 7), CorporateActionType.SPLIT, ratio=Decimal("2")))
    reports = validate_ohlcv_series(half, run_id="r7", corporate_actions=[split])
    assert len(reports) == 1
    assert reports[0].status is ValidationStatus.PASS
    assert reports[0].matching_corporate_action_id == 77

    wrong_ratio = [
        make_row("TCS", date(2025, 1, 6), "100"),
        make_row("TCS", date(2025, 1, 7), "150"),
    ]
    reports = validate_ohlcv_series(wrong_ratio, run_id="r8", corporate_actions=[split])
    assert len(reports) == 1 and reports[0].status is ValidationStatus.FAIL, (
        "a nearby split with the wrong predicted magnitude must not auto-pass"
    )

    rights = (5, CorporateAction("TCS", date(2025, 1, 7), CorporateActionType.RIGHTS, ratio=Decimal("1")))
    reports = validate_ohlcv_series(jump, run_id="r9", corporate_actions=[rights])
    assert len(reports) == 1 and reports[0].status is ValidationStatus.WARN

    try:
        validate_ohlcv_series(jump, run_id="r10", suspicious_return_threshold=float("nan"))
        raise AssertionError("NaN threshold should raise")
    except ValueError:
        pass

    try:
        validate_ohlcv_series(
            [make_row("TCS", date(2025, 1, 6), "100"), make_row("INFY", date(2025, 1, 7), "100")],
            run_id="r11",
        )
        raise AssertionError("mixed tickers should raise")
    except ValueError:
        pass

    tcs_fail = validate_ohlcv_series(dup, run_id="r12")
    infy_dup = [
        make_row("INFY", date(2025, 1, 6), "500"),
        make_row("INFY", date(2025, 1, 6), "500"),
    ]
    infy_fail = validate_ohlcv_series(infy_dup, run_id="r12")
    keys = rejected_keys(tcs_fail + infy_fail)
    assert keys == {("TCS", date(2025, 1, 6)), ("INFY", date(2025, 1, 6))}, keys

    unsorted = [
        make_row("TCS", date(2025, 1, 7), "101"),
        make_row("TCS", date(2025, 1, 6), "100"),
    ]
    reports = validate_ohlcv_series(unsorted, run_id="r13")
    assert any(r.message and "not in trade_date order" in r.message for r in reports)


if __name__ == "__main__":
    self_check()
    print("self-check passed")