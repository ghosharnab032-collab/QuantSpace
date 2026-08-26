"""
data/loaders.py
---------------
Load raw OHLCV rows from external sources.

Responsibilities:
    - Source-specific parsing
    - Field-name mapping
    - Date parsing
    - Source metadata

Common output shape:

    ticker
    trade_date
    open
    high
    low
    close
    volume
    source
    source_file

Loaders do NOT:
    - perform OHLC validation
    - convert prices to Decimal
    - write to Turso

Those responsibilities belong to normalization.py,
validation.py, and ingest.py respectively.

Supported sources:
    - Generic CSV
    - NSE UDiFF Bhavcopy
    - NSE historical API via NseIndiaApi
"""

from __future__ import annotations

import csv
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from data.schemas import DataSource


# ============================================================================
# DATE PARSING
# ============================================================================

def _parse_date(
    value: object,
    *,
    field_name: str = "date",
) -> date:
    """
    Parse a source date into Python date.

    Supported formats:
        YYYY-MM-DD
        DD-MMM-YYYY
    """

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string or date; "
            f"got {type(value).__name__}."
        )

    value = value.strip()

    if not value:
        raise ValueError(
            f"{field_name} is empty."
        )

    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    try:
        return datetime.strptime(
            value,
            "%d-%b-%Y",
        ).date()
    except ValueError as error:
        raise ValueError(
            f"{field_name}={value!r} "
            "is not a supported date format."
        ) from error


# ============================================================================
# GENERAL CSV HELPERS
# ============================================================================

def _normalise_keys(
    row: dict[str, Any],
) -> dict[str, Any]:
    """Normalize source column names."""

    return {
        key.strip().lower()
        if key
        else "": value
        for key, value in row.items()
    }


def _require_fields(
    row: dict[str, Any],
    required: tuple[str, ...],
) -> None:
    """Raise a clear error when required fields are missing."""

    missing = [
        field
        for field in required
        if field not in row
    ]

    if missing:
        raise ValueError(
            "Missing required field(s): "
            + ", ".join(missing)
            + "."
        )


# ============================================================================
# GENERIC CSV LOADER
# ============================================================================

def load_csv(
    filepath: str | Path,
) -> list[dict[str, Any]]:
    """
    Load raw OHLCV records from a local CSV file.

    Supported ticker fields:
        ticker
        symbol

    Required fields:
        date
        open
        high
        low
        close

    Optional:
        volume
    """

    path = Path(filepath)

    if not path.is_file():
        raise FileNotFoundError(
            f"CSV file not found: {filepath}"
        )

    with path.open(
        newline="",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(
                "CSV file has no header."
            )

        field_names = {
            field.strip().lower()
            for field in reader.fieldnames
            if field
        }

        if "date" not in field_names:
            raise ValueError(
                "CSV must contain a 'date' column."
            )

        if (
            "ticker" not in field_names
            and "symbol" not in field_names
        ):
            raise ValueError(
                "CSV must contain either "
                "a 'ticker' or 'symbol' column."
            )

        required_price_fields = {
            "open",
            "high",
            "low",
            "close",
        }

        missing_prices = (
            required_price_fields
            - field_names
        )

        if missing_prices:
            raise ValueError(
                "CSV is missing required OHLC "
                "field(s): "
                + ", ".join(
                    sorted(missing_prices)
                )
            )

        rows: list[dict[str, Any]] = []

        for line_number, raw_row in enumerate(
            reader,
            start=2,
        ):

            row = _normalise_keys(raw_row)

            try:
                ticker = (
                    row.get("ticker")
                    or row.get("symbol")
                )

                if ticker is None:
                    raise ValueError(
                        "ticker/symbol is empty."
                    )

                ticker = str(ticker).strip().upper()

                if not ticker:
                    raise ValueError(
                        "ticker/symbol is empty."
                    )

                trade_date = _parse_date(
                    row["date"]
                )

                rows.append(
                    {
                        "ticker": ticker,
                        "trade_date": trade_date,
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row.get("volume"),
                        "source": DataSource.CSV_EXPORT,
                        "source_file": str(path),
                    }
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ) as error:

                raise ValueError(
                    f"Invalid CSV row at "
                    f"line {line_number}: {error}"
                ) from error

    return rows


# ============================================================================
# NSE UDIFF BHAVCOPY LOADER
# ============================================================================

def _load_nse_bhavcopy_reader(
    reader: csv.DictReader,
    source_file: str,
) -> list[dict[str, Any]]:
    """
    Convert an NSE UDiFF CSV reader into the common raw schema.

    Only normal equity instruments are loaded:
        FinInstrmTp = STK
        SctySrs = EQ
    """

    if not reader.fieldnames:
        raise ValueError(
            "NSE UDiFF CSV has no header."
        )

    field_names = {
        field.strip()
        for field in reader.fieldnames
        if field
    }

    required_fields = {
        "TradDt",
        "TckrSymb",
        "FinInstrmTp",
        "SctySrs",
        "OpnPric",
        "HghPric",
        "LwPric",
        "ClsPric",
        "TtlTradgVol",
    }

    missing = required_fields - field_names

    if missing:
        raise ValueError(
            "NSE UDiFF CSV is missing required "
            "field(s): "
            + ", ".join(sorted(missing))
        )

    rows: list[dict[str, Any]] = []

    for line_number, raw_row in enumerate(
        reader,
        start=2,
    ):

        row = {
            key.strip(): value
            for key, value in raw_row.items()
            if key is not None
        }

        instrument_type = str(
            row.get("FinInstrmTp", "")
        ).strip().upper()

        security_series = str(
            row.get("SctySrs", "")
        ).strip().upper()

        if instrument_type != "STK":
            continue

        if security_series != "EQ":
            continue

        try:
            ticker = str(
                row["TckrSymb"]
            ).strip().upper()

            if not ticker:
                raise ValueError(
                    "TckrSymb is empty."
                )

            trade_date = _parse_date(
                row["TradDt"],
                field_name="TradDt",
            )

            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": trade_date,
                    "open": row["OpnPric"],
                    "high": row["HghPric"],
                    "low": row["LwPric"],
                    "close": row["ClsPric"],
                    "volume": row["TtlTradgVol"],
                    "source": DataSource.NSE_BHAVCOPY,
                    "source_file": source_file,
                }
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                f"Invalid NSE UDiFF row at "
                f"line {line_number}: {error}"
            ) from error

    return rows


def load_nse_bhavcopy(
    filepath: str | Path,
) -> list[dict[str, Any]]:
    """
    Load an NSE UDiFF CM Bhavcopy CSV or ZIP.

    Accepted input:
        .csv
        .zip containing the NSE UDiFF CSV
    """

    path = Path(filepath)

    if not path.is_file():
        raise FileNotFoundError(
            f"NSE Bhavcopy not found: {filepath}"
        )

    suffix = path.suffix.lower()

    if suffix == ".zip":

        with zipfile.ZipFile(path, "r") as archive:

            csv_names = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".csv")
                and not name.endswith("/")
            ]

            if not csv_names:
                raise ValueError(
                    "NSE Bhavcopy ZIP contains "
                    "no CSV file."
                )

            if len(csv_names) > 1:
                raise ValueError(
                    "NSE Bhavcopy ZIP contains "
                    "multiple CSV files; expected one."
                )

            csv_name = csv_names[0]

            with archive.open(
                csv_name,
                "r",
            ) as raw_file:

                import io

                text_file = io.TextIOWrapper(
                    raw_file,
                    encoding="utf-8-sig",
                    newline="",
                )

                reader = csv.DictReader(
                    text_file
                )

                return _load_nse_bhavcopy_reader(
                    reader,
                    str(path),
                )

    if suffix == ".csv":

        with path.open(
            newline="",
            encoding="utf-8-sig",
        ) as file:

            reader = csv.DictReader(file)

            return _load_nse_bhavcopy_reader(
                reader,
                str(path),
            )

    raise ValueError(
        "NSE Bhavcopy must be a .csv "
        "or .zip file."
    )


# ============================================================================
# NSE HISTORICAL API LOADER
# ============================================================================

def load_nse(
    symbol: str,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    """
    Load historical NSE equity data using NseIndiaApi.

    Package:
        BennyThadikaran/NseIndiaApi

    Returns the project's common raw OHLCV schema.

    NSE response mapping:

        chSymbol         -> ticker
        mtimestamp       -> trade_date
        chOpeningPrice   -> open
        chTradeHighPrice -> high
        chTradeLowPrice  -> low
        chClosingPrice   -> close
        chTotTradedQty   -> volume
    """

    symbol = symbol.strip().upper()

    if not symbol:
        raise ValueError(
            "NSE symbol cannot be empty."
        )

    start_date = _parse_date(
        start,
        field_name="start",
    )

    end_date = _parse_date(
        end,
        field_name="end",
    )

    if start_date > end_date:
        raise ValueError(
            "`start` date cannot be after "
            "`end` date."
        )

    try:
        from nse import NSE
    except ImportError as error:
        raise RuntimeError(
            "NseIndiaApi is required for NSE "
            "historical data.\n"
            "Install it with:\n"
            "python -m pip install -U "
            "git+https://github.com/"
            "BennyThadikaran/NseIndiaApi.git"
        ) from error

    nse = NSE(
        download_folder="",
        server=False,
    )

    try:
        raw = nse.fetch_equity_historical_data(
            symbol,
            start_date,
            end_date,
            series="EQ",
        )
    finally:
        nse.exit()

    if raw is None:
        return []

    if not isinstance(raw, list):
        raise ValueError(
            "Unexpected response format from "
            "NseIndiaApi."
        )

    rows: list[dict[str, Any]] = []

    for row_number, raw_row in enumerate(
        raw,
        start=1,
    ):

        if not isinstance(raw_row, dict):
            raise ValueError(
                f"NSE historical row "
                f"{row_number} is not an object."
            )

        try:
            ticker = str(
                raw_row.get(
                    "chSymbol",
                    symbol,
                )
            ).strip().upper()

            if not ticker:
                ticker = symbol

            trade_date = _parse_date(
                raw_row["mtimestamp"],
                field_name="mtimestamp",
            )

            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": trade_date,
                    "open": raw_row["chOpeningPrice"],
                    "high": raw_row["chTradeHighPrice"],
                    "low": raw_row["chTradeLowPrice"],
                    "close": raw_row["chClosingPrice"],
                    "volume": raw_row["chTotTradedQty"],
                    "source": DataSource.NSE_API,
                    "source_file": None,
                }
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                f"Invalid NSE historical row "
                f"{row_number}: {error}"
            ) from error

    return rows


# ============================================================================
# SELF CHECK
# ============================================================================

def self_check() -> None:
    """Basic loader checks without network access."""

    import tempfile

    csv_content = """ticker,date,open,high,low,close,volume
TCS,2025-01-06,100,102,99,101,100000
INFY,06-Jan-2025,200,205,198,203,"200,000"
"""

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        encoding="utf-8",
        delete=False,
    ) as file:

        file.write(csv_content)
        filepath = file.name

    try:

        rows = load_csv(filepath)

        assert len(rows) == 2
        assert rows[0]["ticker"] == "TCS"

        assert rows[0]["trade_date"] == date(
            2025,
            1,
            6,
        )

        assert rows[0]["open"] == "100"
        assert rows[0]["volume"] == "100000"

        assert (
            rows[0]["source"]
            == DataSource.CSV_EXPORT
        )

        assert rows[1]["ticker"] == "INFY"

        assert rows[1]["trade_date"] == date(
            2025,
            1,
            6,
        )

        print("1. Generic CSV loading: OK")
        print("2. Date parsing: OK")
        print("3. Field mapping: OK")
        print("4. Common output shape: OK")

    finally:

        Path(filepath).unlink(
            missing_ok=True
        )

    print("self-check passed")


# ============================================================================
# CLI
# ============================================================================

def main() -> None:
    """
    Run loader self-check.

    The loader does not write to the database.
    Ingestion is handled by data.ingest.
    """

    self_check()


if __name__ == "__main__":
    main()