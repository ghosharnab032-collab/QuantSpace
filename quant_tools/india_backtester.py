"""A focused India-first daily backtester for a moving-average strategy.

CSV columns required: Date, Open, High, Low, Close (case-insensitive).
Signals use a day's close and execute at the next day's open, avoiding
look-ahead bias. Costs are simplified delivery-equity estimates.

Requires: numpy, pandas
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    """Load a daily OHLCV CSV with a normalized datetime index."""
    frame = pd.read_csv(path)
    names = {column: str(column).strip().lower().replace(" ", "_") for column in frame.columns}
    frame = frame.rename(columns=names)
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    for column in required - {"date"}:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if frame["date"].duplicated().any():
        raise ValueError("CSV contains duplicate dates.")
    frame = frame.sort_values("date").set_index("date")
    if len(frame) < 2 or (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Need two rows with positive OHLC prices.")
    if ((frame["high"] < frame[["open", "close"]].max(axis=1)) | (frame["low"] > frame[["open", "close"]].min(axis=1))).any():
        raise ValueError("OHLC values are inconsistent.")
    return frame


@dataclass(frozen=True)
class IndiaEquityDeliveryCost:
    """Simplified one-way delivery-equity cost rates; confirm against contract notes."""
    stt: float = 0.001
    stamp_buy: float = 0.00015
    sebi: float = 0.000001
    brokerage: float = 0.0003
    exchange_service: float = 0.00005
    gst: float = 0.18

    def transaction_cost(self, notional: float, side: str) -> float:
        if notional < 0 or side not in {"BUY", "SELL"}:
            raise ValueError("notional must be non-negative and side must be BUY or SELL.")
        services = notional * (self.brokerage + self.exchange_service)
        return notional * (self.stt + self.sebi + (self.stamp_buy if side == "BUY" else 0)) + services * (1 + self.gst)


def moving_average_signal(close: pd.Series, fast: int = 20, slow: int = 50) -> pd.Series:
    """Long/flat signal, shifted so it can only trade on the next bar."""
    if fast <= 0 or slow <= fast:
        raise ValueError("Require 0 < fast < slow.")
    signal = (close.rolling(fast).mean() > close.rolling(slow).mean()).astype(float).shift(1)
    return signal.fillna(0.0)


@dataclass(frozen=True)
class BacktestResult:
    gross_equity: pd.Series
    net_equity: pd.Series
    daily_returns: pd.Series
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    max_drawdown: float
    trades: int
    total_costs: float

    def summary(self) -> dict[str, float | int]:
        return {
            "total_return": self.total_return,
            "cagr": self.cagr,
            "volatility": self.volatility,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "trades": self.trades,
            "total_costs": self.total_costs,
            "gross_final_wealth": float(self.gross_equity.iloc[-1]),
            "net_final_wealth": float(self.net_equity.iloc[-1]),
        }


class IndiaBacktester:
    """Single-asset, long/flat backtester with next-open execution."""
    def __init__(self, data: pd.DataFrame, initial_capital: float = 100_000, risk_free_rate: float = 0.068, costs: IndiaEquityDeliveryCost | None = None):
        if initial_capital <= 0 or not np.isfinite([initial_capital, risk_free_rate]).all() or risk_free_rate < 0:
            raise ValueError("initial_capital must be positive; risk_free_rate must be finite and non-negative.")
        if {"open", "close"} - set(data.columns):
            raise ValueError("data needs open and close columns.")
        self.data, self.initial_capital, self.risk_free_rate = data.sort_index(), float(initial_capital), float(risk_free_rate)
        self.costs = costs or IndiaEquityDeliveryCost()

    def run(self, signal: pd.Series) -> BacktestResult:
        position = signal.reindex(self.data.index).fillna(0.0).astype(float)
        if ((position < 0) | (position > 1)).any():
            raise ValueError("signal must be long/flat, with values in [0, 1].")

        gross, net, total_costs, trades = self.initial_capital, self.initial_capital, 0.0, 0
        gross_values, net_values = [], []
        for index, timestamp in enumerate(self.data.index):
            current = position.iloc[index]
            previous = 0.0 if index == 0 else position.iloc[index - 1]
            open_price, close_price = self.data.loc[timestamp, ["open", "close"]]
            overnight = 0.0 if index == 0 else open_price / self.data["close"].iloc[index - 1] - 1.0

            # Portfolio value after overnight gap (previous position)
            gross_at_open = gross * (1.0 + previous * overnight)
            net_at_open = net * (1.0 + previous * overnight)

            # Trade at open
            change = current - previous
            if abs(change) > 1e-12:
                cost = self.costs.transaction_cost(net_at_open * abs(change), "BUY" if change > 0 else "SELL")
                net_at_open -= cost
                total_costs += cost
                trades += 1

            # Intraday return on current position
            intraday = current * (close_price / open_price - 1.0)
            gross = gross_at_open * (1.0 + intraday)
            net = net_at_open * (1.0 + intraday)

            gross_values.append(gross)
            net_values.append(net)

        gross_equity = pd.Series(gross_values, index=self.data.index)
        net_equity = pd.Series(net_values, index=self.data.index)
        returns = net_equity.pct_change().fillna(0.0)
        years = len(net_equity) / TRADING_DAYS
        volatility = float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))
        rf_daily = (1 + self.risk_free_rate) ** (1 / TRADING_DAYS) - 1
        sharpe = float((returns.mean() - rf_daily) * TRADING_DAYS / volatility) if volatility > 1e-12 else 0.0
        return BacktestResult(
            gross_equity=gross_equity,
            net_equity=net_equity,
            daily_returns=returns,
            total_return=float(net / self.initial_capital - 1),
            cagr=float((net / self.initial_capital) ** (1 / years) - 1),
            volatility=volatility,
            sharpe=sharpe,
            max_drawdown=float((net_equity / net_equity.cummax() - 1).min()),
            trades=trades,
            total_costs=float(total_costs),
        )


def train_test_split(data: pd.DataFrame, split_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    split = pd.Timestamp(split_date)
    train, test = data.loc[data.index < split].copy(), data.loc[data.index >= split].copy()
    if train.empty or test.empty:
        raise ValueError("split_date must produce non-empty train and test sets.")
    return train, test


def self_check() -> None:
    # Check 1: basic long/flat with one trade
    dates = pd.date_range("2025-01-01", periods=3, freq="B")
    data = pd.DataFrame({"open": [100, 101, 102], "close": [101, 102, 103]}, index=dates)
    result = IndiaBacktester(data, risk_free_rate=0).run(pd.Series([0, 1, 1], index=dates))
    assert result.trades == 1 and result.net_equity.iloc[-1] > 0, "basic backtest failed"

    # Check 2: costs are deducted
    result_cost = IndiaBacktester(data, costs=IndiaEquityDeliveryCost(brokerage=0.01)).run(pd.Series([0, 1, 1], index=dates))
    assert result_cost.total_costs > 0, "costs not deducted"
    assert result_cost.net_equity.iloc[-1] < result.net_equity.iloc[-1], "net should be lower with costs"

    # Check 3: MA signal generation
    ma_data = pd.DataFrame({"open": [100]*60, "close": list(range(100, 160))}, index=pd.date_range("2025-01-01", periods=60, freq="B"))
    signal = moving_average_signal(ma_data["close"], fast=10, slow=20)
    assert signal.iloc[0] == 0.0, "signal should be flat before slow MA is available"
    assert signal.notna().all(), "signal should have no NaN after warm-up"

    # Check 4: train/test split
    train, test = train_test_split(ma_data, "2025-03-01")
    assert len(train) > 0 and len(test) > 0, "split should produce non-empty sets"

    # Check 5: compounding correctness
    # Day 1: close=100, position=1. Day 2: open=110, close=121, position=1.
    # True return = (110/100) * (121/110) - 1 = 121/100 - 1 = 21%
    dates = pd.date_range("2025-01-01", periods=2, freq="B")
    gap_data = pd.DataFrame({"open": [100, 110], "close": [100, 121]}, index=dates)
    zero_costs = IndiaEquityDeliveryCost(stt=0, stamp_buy=0, sebi=0, brokerage=0, exchange_service=0, gst=0)
    gap_result = IndiaBacktester(gap_data, risk_free_rate=0, costs=zero_costs).run(pd.Series([1, 1], index=dates))
    expected_return = 121 / 100 - 1.0  # 21%
    actual_return = gap_result.net_equity.iloc[-1] / 100_000 - 1.0
    assert abs(actual_return - expected_return) < 1e-10, f"compounding bug: expected {expected_return}, got {actual_return}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, nargs="?")
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=50)
    parser.add_argument("--split-date")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("self-check passed")
    elif args.csv:
        data = load_ohlcv_csv(args.csv)
        if args.split_date:
            train, data = train_test_split(data, args.split_date)
            print(f"Train: {len(train)} rows | Test: {len(data)} rows")
        signal = moving_average_signal(data["close"], fast=args.fast, slow=args.slow)
        result = IndiaBacktester(data).run(signal)
        print(json.dumps(result.summary(), indent=2))
    else:
        parser.error("provide a CSV or use --self-check")
    