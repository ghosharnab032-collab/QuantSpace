from data.df_adapter import get_price_dataframe


def main():
    print("=== DATAFRAME ADAPTER TEST ===")

    data = get_price_dataframe(
        "RELIANCE",
        start_date="2026-08-19",
        end_date="2026-08-19",
    )

    print("[PASS] DataFrame loaded")
    print(f"Rows: {len(data)}")
    print(f"Columns: {list(data.columns)}")
    print(f"Index: {data.index.name}")
    print(data)

    assert data.index.name == "date"
    assert {"open", "high", "low", "close"} <= set(data.columns)
    assert len(data) > 0

    print("\nDataFrame adapter smoke test PASSED.")


if __name__ == "__main__":
    main()