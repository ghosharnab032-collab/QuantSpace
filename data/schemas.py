"""
schemas.py — Canonical domain schemas for the quant data pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from math import isfinite
from typing import Optional


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"


class InstrumentType(str, Enum):
    EQUITY = "EQ"
    ETF = "ETF"
    INDEX = "IDX"
    REIT = "REIT"
    INVIT = "INVIT"
    SGB = "SGB"
    GSEC = "GSEC"


class CorporateActionType(str, Enum):
    SPLIT = "split"
    BONUS = "bonus"
    RIGHTS = "rights"
    DIVIDEND = "dividend"
    MERGER = "merger"
    DEMERGER = "demerger"


class ReturnFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ReturnType(str, Enum):
    SIMPLE = "simple"
    LOG = "log"


class DataSource(str, Enum):
    NSE_BHAVCOPY = "nse_bhavcopy"
    NSE_API = "nse_api"
    BSE_BHAVCOPY = "bse_bhavcopy"
    CSV_EXPORT = "csv_export"
    YAHOO_FINANCE = "yahoo_finance"
    RBI = "rbi"
    MANUAL_ENTRY = "manual"


class ValidationStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class AssetMetadata:
    ticker: str
    name: str
    exchange: Exchange
    instrument_type: InstrumentType
    isin: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    face_value: Optional[Decimal] = None
    first_listed: Optional[date] = None
    last_traded: Optional[date] = None
    benchmark_index: Optional[str] = None
    tax_type: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("ticker cannot be empty.")
        if not self.name.strip():
            raise ValueError("name cannot be empty.")
        if self.face_value is not None:
            if not self.face_value.is_finite():
                raise ValueError("face_value must be finite.")
            if self.face_value <= 0:
                raise ValueError("face_value must be positive.")


@dataclass(frozen=True, slots=True)
class OHLCV:
    ticker: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Optional[int] = None
    source: DataSource = DataSource.CSV_EXPORT
    source_file: Optional[str] = None
    ingested_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("ticker cannot be empty.")
        prices = (self.open, self.high, self.low, self.close)
        for price in prices:
            if not isinstance(price, Decimal):
                raise TypeError("OHLC prices must be Decimal values.")
            if not price.is_finite():
                raise ValueError("OHLC prices must be finite.")
            if price <= 0:
                raise ValueError("OHLC prices must be positive.")
        if self.high < max(self.open, self.close):
            raise ValueError("high must be >= both open and close.")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be <= both open and close.")
        if self.volume is not None:
            if not isinstance(self.volume, int):
                raise TypeError("volume must be an integer or None.")
            if self.volume < 0:
                raise ValueError("volume cannot be negative.")


@dataclass(frozen=True, slots=True)
class CorporateAction:
    ticker: str
    ex_date: date
    action_type: CorporateActionType
    ratio: Optional[Decimal] = None
    value: Optional[Decimal] = None
    description: Optional[str] = None
    source: DataSource = DataSource.NSE_API
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("ticker cannot be empty.")
        requires_ratio = {CorporateActionType.SPLIT, CorporateActionType.BONUS, CorporateActionType.RIGHTS}
        if self.action_type in requires_ratio:
            if self.ratio is None:
                raise ValueError(f"{self.action_type.value} requires a ratio.")
            if not self.ratio.is_finite():
                raise ValueError(f"{self.action_type.value} ratio must be finite.")
            if self.ratio <= 0:
                raise ValueError(f"{self.action_type.value} ratio must be positive.")
        if self.action_type is CorporateActionType.DIVIDEND:
            if self.value is None:
                raise ValueError("dividend requires a value.")
            if not self.value.is_finite():
                raise ValueError("dividend value must be finite.")
            if self.value < 0:
                raise ValueError("dividend value cannot be negative.")
        if self.value is not None and not self.value.is_finite():
            raise ValueError("corporate-action value must be finite.")
        if self.ratio is not None and not self.ratio.is_finite():
            raise ValueError("corporate-action ratio must be finite.")


@dataclass(frozen=True, slots=True)
class ReturnObservation:
    ticker: str
    observation_date: date
    return_value: float
    return_type: ReturnType = ReturnType.LOG
    frequency: ReturnFrequency = ReturnFrequency.DAILY

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("ticker cannot be empty.")
        if not isfinite(self.return_value):
            raise ValueError("return_value must be finite.")
        if self.return_type is ReturnType.SIMPLE and self.return_value <= -1:
            raise ValueError("simple return cannot be <= -100%.")


@dataclass(frozen=True, slots=True)
class ValidationReport:
    run_id: str
    ticker: str
    trade_date: date
    status: ValidationStatus
    message: Optional[str] = None
    matching_corporate_action_id: Optional[int] = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id cannot be empty.")
        if not self.ticker.strip():
            raise ValueError("ticker cannot be empty.")
        if self.matching_corporate_action_id is not None and self.matching_corporate_action_id < 0:
            raise ValueError("matching_corporate_action_id cannot be negative.")


@dataclass(frozen=True, slots=True)
class DataRun:
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    source: DataSource = DataSource.CSV_EXPORT
    tickers_processed: int = 0
    rows_inserted: int = 0
    rows_rejected: int = 0
    rows_warned: int = 0
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id cannot be empty.")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at.")
        counts = (self.tickers_processed, self.rows_inserted, self.rows_rejected, self.rows_warned)
        if any(count < 0 for count in counts):
            raise ValueError("tickers_processed/rows_inserted/rows_rejected/rows_warned cannot be negative.")


def validate_ticker(ticker: str) -> str:
    cleaned = ticker.strip().upper().replace(" ", "")
    if not cleaned:
        raise ValueError("ticker must contain at least one character.")
    if len(cleaned) > 20:
        raise ValueError("ticker must contain 1-20 characters.")
    return cleaned


def validate_date(value: date) -> date:
    if value > datetime.now(UTC).date():
        raise ValueError(f"date {value} is in the future.")
    return value


def self_check() -> None:
    from datetime import timedelta

    row = OHLCV(
        ticker="NIFTYBEES", trade_date=date(2025, 1, 1),
        open=Decimal("100"), high=Decimal("102"), low=Decimal("99"), close=Decimal("101"),
        volume=1_000_000, source=DataSource.NSE_BHAVCOPY,
    )
    assert row.close == Decimal("101")

    bad_cases = [
        (Decimal("100"), Decimal("98"), Decimal("99"), Decimal("101")),
        (Decimal("100"), Decimal("100"), Decimal("99"), Decimal("101")),
        (Decimal("100"), Decimal("102"), Decimal("101"), Decimal("99")),
        (Decimal("0"), Decimal("102"), Decimal("99"), Decimal("101")),
    ]
    for o, h, l, c in bad_cases:
        try:
            OHLCV("TCS", date(2025, 1, 15), o, h, l, c)
            raise AssertionError("should have raised")
        except ValueError:
            pass

    try:
        OHLCV("TCS", date(2025, 1, 15), Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), volume=-1)
        raise AssertionError("negative volume should raise")
    except ValueError:
        pass

    try:
        CorporateAction("RELIANCE", date(2024, 9, 20), CorporateActionType.SPLIT)
        raise AssertionError("split without ratio should raise")
    except ValueError:
        pass

    split = CorporateAction("RELIANCE", date(2024, 9, 20), CorporateActionType.SPLIT, ratio=Decimal("2"))
    assert split.ratio == Decimal("2")
    assert Decimal("1") / split.ratio == Decimal("0.5")

    bonus = CorporateAction("RELIANCE", date(2024, 9, 20), CorporateActionType.BONUS, ratio=Decimal("1"))
    assert Decimal("1") / (Decimal("1") + bonus.ratio) == Decimal("0.5")

    rights = CorporateAction("RELIANCE", date(2024, 9, 20), CorporateActionType.RIGHTS, ratio=Decimal("0.25"))
    assert rights.ratio == Decimal("0.25")

    try:
        CorporateAction("RELIANCE", date(2024, 9, 20), CorporateActionType.DIVIDEND, value=Decimal("-5"))
        raise AssertionError("negative dividend should raise")
    except ValueError:
        pass

    tomorrow = datetime.now(UTC).date() + timedelta(days=1)
    try:
        validate_date(tomorrow)
        raise AssertionError("future date should raise")
    except ValueError:
        pass

    try:
        validate_ticker("   ")
        raise AssertionError("empty ticker should raise")
    except ValueError:
        pass

    assert validate_ticker("  reliance  ") == "RELIANCE"

    try:
        ReturnObservation("TCS", date(2025, 1, 15), -1.0, return_type=ReturnType.SIMPLE)
        raise AssertionError("simple return = -100% should raise")
    except ValueError:
        pass

    ret = ReturnObservation("TCS", date(2025, 1, 15), -1.0, return_type=ReturnType.LOG)
    assert ret.return_value == -1.0

    asset = AssetMetadata(
        ticker="RELIANCE", name="Reliance Industries Ltd.", exchange=Exchange.NSE,
        instrument_type=InstrumentType.EQUITY, sector="Energy", tax_type="equity",
    )
    assert asset.exchange is Exchange.NSE

    try:
        AssetMetadata(ticker="TCS", name="", exchange=Exchange.NSE, instrument_type=InstrumentType.EQUITY)
        raise AssertionError("empty name should raise")
    except ValueError:
        pass

    run = DataRun(run_id="run_001", started_at=datetime.now(UTC), source=DataSource.CSV_EXPORT)
    assert run.rows_inserted == 0

    report = ValidationReport(
        run_id="run_001", ticker="RELIANCE", trade_date=date(2025, 1, 7),
        status=ValidationStatus.PASS, message="2-for-1 split explained price movement.",
        matching_corporate_action_id=77,
    )
    assert report.matching_corporate_action_id == 77


if __name__ == "__main__":
    self_check()
    print("self-check passed")