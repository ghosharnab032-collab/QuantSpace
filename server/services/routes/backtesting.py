"""Backtesting API routes."""

from __future__ import annotations

from datetime import date

import pandas as pd

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database.connections import get_connection

from quant_tools.india_backtester import (
    IndiaBacktester,
    IndiaEquityDeliveryCost,
    moving_average_signal,
)


router = APIRouter(
    prefix="/backtesting",
    tags=["backtesting"],
)


# ============================================================
# REQUEST MODEL
# ============================================================


class BacktestRequest(BaseModel):
    ticker: str = Field(
        ...,
        min_length=1,
    )

    start: date | None = None
    end: date | None = None

    fast_ma: int = Field(
        default=20,
        ge=1,
    )

    slow_ma: int = Field(
        default=50,
        ge=2,
    )

    initial_capital: float = Field(
        default=100_000,
        gt=0,
    )

    risk_free_rate: float = Field(
        default=0.068,
        ge=0,
    )

    # Optional explicit India delivery costs.
    stt: float = Field(
        default=0.001,
        ge=0,
    )

    stamp_buy: float = Field(
        default=0.00015,
        ge=0,
    )

    sebi: float = Field(
        default=0.000001,
        ge=0,
    )

    brokerage: float = Field(
        default=0.0003,
        ge=0,
    )

    exchange_service: float = Field(
        default=0.00005,
        ge=0,
    )

    gst: float = Field(
        default=0.18,
        ge=0,
    )


# ============================================================
# HELPERS
# ============================================================


def load_price_data(
    ticker: str,
    start: date | None,
    end: date | None,
) -> pd.DataFrame:

    ticker = ticker.strip().upper()

    conn = get_connection()

    try:
        sql = """
            SELECT
                trade_date,
                open,
                high,
                low,
                close,
                volume
            FROM (
                SELECT
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    source,
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY trade_date
                        ORDER BY
                            CASE
                                WHEN source = 'nse_api' THEN 1
                                WHEN source = 'nse_bhavcopy' THEN 2
                                ELSE 3
                            END,
                            id ASC
                    ) AS rn
                FROM price_daily
                WHERE ticker = ?
        """

        params: list[object] = [
            ticker
        ]

        if start:
            sql += """
                AND trade_date >= ?
            """

            params.append(
                start.isoformat()
            )

        if end:
            sql += """
                AND trade_date <= ?
            """

            params.append(
                end.isoformat()
            )

        sql += """
            )
            WHERE rn = 1
            ORDER BY trade_date ASC
        """

        rows = conn.execute(
            sql,
            tuple(params),
        ).fetchall()

    finally:
        conn.close()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No historical data found for {ticker}.",
        )

    data = pd.DataFrame(
        rows,
        columns=[
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    )

    data["date"] = pd.to_datetime(
        data["date"]
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data = (
        data
        .dropna(
            subset=[
                "open",
                "high",
                "low",
                "close",
            ]
        )
        .sort_values("date")
        .set_index("date")
    )

    return data


# ============================================================
# BACKTEST
# ============================================================


@router.post("")
async def run_backtest(
    request: BacktestRequest,
):
    """
    Run the India-first moving-average backtester.

    Signals are generated using historical closes and
    executed at the next day's open.
    """

    ticker = request.ticker.strip().upper()

    if request.fast_ma >= request.slow_ma:
        raise HTTPException(
            status_code=400,
            detail="fast_ma must be smaller than slow_ma.",
        )

    try:
        data = load_price_data(
            ticker=ticker,
            start=request.start,
            end=request.end,
        )

        minimum_rows = max(
            request.slow_ma + 1,
            2,
        )

        if len(data) < minimum_rows:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"At least {minimum_rows} trading days "
                    f"are required for a {request.slow_ma}-day "
                    "slow moving average."
                ),
            )

        signal = moving_average_signal(
            data["close"],
            fast=request.fast_ma,
            slow=request.slow_ma,
        )

        costs = IndiaEquityDeliveryCost(
            stt=request.stt,
            stamp_buy=request.stamp_buy,
            sebi=request.sebi,
            brokerage=request.brokerage,
            exchange_service=request.exchange_service,
            gst=request.gst,
        )

        backtester = IndiaBacktester(
            data=data,
            initial_capital=request.initial_capital,
            risk_free_rate=request.risk_free_rate,
            costs=costs,
        )

        result = backtester.run(signal)

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Backtest failed: {exc}",
        ) from exc


    # ========================================================
    # EQUITY CURVE
    # ========================================================

    equity = []

    for timestamp in result.net_equity.index:

        gross_value = float(
            result.gross_equity.loc[timestamp]
        )

        net_value = float(
            result.net_equity.loc[timestamp]
        )

        daily_return = float(
            result.daily_returns.loc[timestamp]
        )

        equity.append(
            {
                "date": timestamp.strftime(
                    "%Y-%m-%d"
                ),
                "gross_equity": gross_value,
                "net_equity": net_value,
                "daily_return": daily_return,
            }
        )


    # ========================================================
    # SIGNAL HISTORY
    # ========================================================

    signals = []

    aligned_signal = signal.reindex(
        data.index
    ).fillna(0.0)

    for timestamp in aligned_signal.index:

        signals.append(
            {
                "date": timestamp.strftime(
                    "%Y-%m-%d"
                ),
                "position": float(
                    aligned_signal.loc[timestamp]
                ),
            }
        )


    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "ticker": ticker,

        "strategy": {
            "name": "Moving Average",
            "fast_ma": request.fast_ma,
            "slow_ma": request.slow_ma,
            "execution": "next_open",
            "position_type": "long_flat",
        },

        "parameters": {
            "initial_capital": request.initial_capital,
            "risk_free_rate": request.risk_free_rate,
            "stt": request.stt,
            "stamp_buy": request.stamp_buy,
            "sebi": request.sebi,
            "brokerage": request.brokerage,
            "exchange_service": request.exchange_service,
            "gst": request.gst,
        },

        "period": {
            "start": data.index[0].strftime(
                "%Y-%m-%d"
            ),
            "end": data.index[-1].strftime(
                "%Y-%m-%d"
            ),
            "rows": len(data),
        },

        "metrics": {
            "total_return": result.total_return,
            "cagr": result.cagr,
            "volatility": result.volatility,
            "sharpe": result.sharpe,
            "max_drawdown": result.max_drawdown,
            "trades": result.trades,
            "total_costs": result.total_costs,
            "gross_final_wealth": float(
                result.gross_equity.iloc[-1]
            ),
            "net_final_wealth": float(
                result.net_equity.iloc[-1]
            ),
        },

        "equity_curve": equity,

        "signals": signals,
    }