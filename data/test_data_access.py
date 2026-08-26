"""
Data-access smoke test.

Run from the project root:

    python -m data.test_data_access
"""

from data.data_access import (
    get_asset,
    get_universe,
    get_prices,
    get_latest_price,
    get_prices_bulk,
    get_corporate_actions,
    get_data_run,
)


def check(name, fn):
    """Run one test and print a compact result."""
    try:
        result = fn()
        print(f"[PASS] {name}")
        print(f"       {result}")
        return True
    except Exception as exc:
        print(f"[FAIL] {name}")
        print(f"       {type(exc).__name__}: {exc}")
        return False


def main():
    print("=== DATA ACCESS TEST ===\n")

    passed = 0
    total = 7

    if check(
        "get_asset(RELIANCE)",
        lambda: get_asset("RELIANCE"),
    ):
        passed += 1

    if check(
        "get_universe()",
        lambda: f"{len(get_universe())} assets",
    ):
        passed += 1

    if check(
        "get_prices(RELIANCE)",
        lambda: f"{len(get_prices('RELIANCE'))} price rows",
    ):
        passed += 1

    if check(
        "get_latest_price(RELIANCE)",
        lambda: get_latest_price("RELIANCE"),
    ):
        passed += 1

    if check(
        "get_prices_bulk()",
        lambda: f"{len(get_prices_bulk(['RELIANCE', 'TCS', 'INFY']))} rows",
    ):
        passed += 1

    if check(
        "get_corporate_actions(RELIANCE)",
        lambda: f"{len(get_corporate_actions('RELIANCE'))} corporate actions",
    ):
        passed += 1

    if check(
        "get_data_run(nonexistent)",
        lambda: get_data_run("test_nonexistent_run"),
    ):
        passed += 1

    print("\n=== RESULT ===")
    print(f"{passed}/{total} tests passed.")

    if passed == total:
        print("Data-access layer smoke test PASSED.")
    else:
        print("Data-access layer smoke test FAILED.")


if __name__ == "__main__":
    main()