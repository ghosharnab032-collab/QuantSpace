from datetime import date

from data.trading_calendar import TradingCalendar


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"[PASS] {name}")


def main():
    print("=== NSE TRADING CALENDAR TEST ===\n")

    cal = TradingCalendar()

    # 1. Normal trading day
    check(
        "2026-08-19 is trading day",
        cal.is_trading_day("2026-08-19") is True,
    )

    # 2. Saturday
    check(
        "Saturday is not trading day",
        cal.is_trading_day("2026-08-22") is False,
    )

    # 3. Sunday
    check(
        "Sunday is not trading day",
        cal.is_trading_day("2026-08-23") is False,
    )

    # 4. NSE holiday
    check(
        "Republic Day is holiday",
        cal.is_trading_day("2026-01-26") is False,
    )

    # 5. Holiday detection
    check(
        "Republic Day detected as holiday",
        cal.is_holiday("2026-01-26") is True,
    )

    # 6. Next trading day
    check(
        "Next trading day after Saturday",
        cal.next_trading_day("2026-08-22")
        == date(2026, 8, 24),
    )

    # 7. Previous trading day
    check(
        "Previous trading day before Sunday",
        cal.previous_trading_day("2026-08-23")
        == date(2026, 8, 21),
    )

    # 8. Add trading days
    check(
        "Add 5 trading days",
        cal.add_trading_days("2026-08-19", 5)
        == date(2026, 8, 27),
    )

    # 9. Trading-day count
    check(
        "Trading-day count",
        cal.trading_days_between(
            "2026-08-17",
            "2026-08-21",
        ) == 5,
    )

    # 10. Alignment
    check(
        "Align weekend forward",
        cal.align_to_trading_day(
            "2026-08-22",
            "next",
        ) == date(2026, 8, 24),
    )

    check(
        "Align weekend backward",
        cal.align_to_trading_day(
            "2026-08-22",
            "previous",
        ) == date(2026, 8, 21),
    )

    # 11. Muhurat Trading
    check(
        "2026 Muhurat date detected",
        cal.is_muhurat_trading_day("2026-11-08") is True,
    )

    check(
        "Muhurat is not normal trading day",
        cal.is_trading_day("2026-11-08") is False,
    )

    check(
        "Muhurat is a trading session",
        cal.is_any_trading_session("2026-11-08") is True,
    )

    # 12. Invalid date
    try:
        cal.is_trading_day("2026-99-99")
    except ValueError:
        print("[PASS] Invalid date rejected")
    else:
        raise AssertionError("Invalid date was accepted")

    print("\n=== RESULT ===")
    print("All NSE trading-calendar tests PASSED.")


if __name__ == "__main__":
    main()