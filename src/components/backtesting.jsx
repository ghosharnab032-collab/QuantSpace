import { useMemo, useState } from "react";

import {
  runBacktest,
} from "../api/quant";


/* =========================================================
   HELPERS
   ========================================================= */

function formatMoney(value) {
  if (
    value == null ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  return `₹${Number(value).toLocaleString(
    "en-IN",
    {
      maximumFractionDigits: 0,
    }
  )}`;
}


function formatPercent(value) {
  if (
    value == null ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  return `${(
    Number(value) * 100
  ).toFixed(2)}%`;
}


function formatNumber(
  value,
  digits = 2
) {
  if (
    value == null ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  return Number(value).toFixed(
    digits
  );
}


/* =========================================================
   MAIN
   ========================================================= */

export default function Backtesting() {

  const [ticker, setTicker] =
    useState("RELIANCE");

  const [start, setStart] =
    useState("2021-01-01");

  const [end, setEnd] =
    useState("2026-08-19");

  const [fastMa, setFastMa] =
    useState("20");

  const [slowMa, setSlowMa] =
    useState("50");

  const [initialCapital, setInitialCapital] =
    useState("100000");

  const [riskFreeRate, setRiskFreeRate] =
    useState("0.068");

  const [result, setResult] =
    useState(null);

  const [error, setError] =
    useState("");

  const [loading, setLoading] =
    useState(false);


  /* =======================================================
     RUN BACKTEST
     ======================================================= */

  async function handleSubmit(event) {
    event.preventDefault();

    setError("");
    setResult(null);

    const symbol =
      ticker.trim().toUpperCase();

    if (!symbol) {
      setError(
        "Enter a ticker."
      );

      return;
    }

    if (
      Number(fastMa) >=
      Number(slowMa)
    ) {
      setError(
        "Fast MA must be smaller than Slow MA."
      );

      return;
    }

    if (start > end) {
      setError(
        "Start date cannot be after end date."
      );

      return;
    }

    setLoading(true);

    try {

      const data =
        await runBacktest({
          ticker: symbol,
          start,
          end,
          fastMa,
          slowMa,
          initialCapital,
          riskFreeRate,
        });

      setResult(data);

    } catch (err) {

      const detail =
        err?.response?.data?.detail;

      if (Array.isArray(detail)) {
        setError(
          detail
            .map(
              (item) => item.msg
            )
            .join(", ")
        );
      } else {
        setError(
          detail ||
          err?.message ||
          "Unable to run backtest."
        );
      }

    } finally {
      setLoading(false);
    }
  }


  return (
    <section className="backtesting-page">

      {/* =================================================
          HEADER
          ================================================= */}

      <div className="tool-page-header">

        <span className="eyebrow">
          STRATEGY RESEARCH
        </span>

        <h1>
          Backtesting
        </h1>

        <p>
          Test quantitative strategies against
          historical market data.
        </p>

      </div>


      {/* =================================================
          CONFIGURATION
          ================================================= */}

      <form
        className="backtest-form"
        onSubmit={handleSubmit}
      >

        <div className="backtest-form-section">

          <div className="backtest-section-heading">

            <div>

              <span className="eyebrow">
                STRATEGY
              </span>

              <h2>
                Moving Average
              </h2>

            </div>

            <span className="strategy-badge">
              LONG / FLAT
            </span>

          </div>


          <div className="backtest-grid">

            <div className="backtest-field full-width">

              <label>
                Ticker
              </label>

              <input
                value={ticker}
                onChange={(event) =>
                  setTicker(
                    event.target.value
                  )
                }
                placeholder="RELIANCE"
              />

            </div>


            <div className="backtest-field">

              <label>
                Fast MA
              </label>

              <input
                type="number"
                min="1"
                value={fastMa}
                onChange={(event) =>
                  setFastMa(
                    event.target.value
                  )
                }
              />

            </div>


            <div className="backtest-field">

              <label>
                Slow MA
              </label>

              <input
                type="number"
                min="2"
                value={slowMa}
                onChange={(event) =>
                  setSlowMa(
                    event.target.value
                  )
                }
              />

            </div>

          </div>

        </div>


        {/* =================================================
            PERIOD
            ================================================= */}

        <div className="backtest-form-section">

          <div className="backtest-section-heading">

            <div>

              <span className="eyebrow">
                PERIOD
              </span>

              <h2>
                Historical data
              </h2>

            </div>

          </div>


          <div className="backtest-grid">

            <div className="backtest-field">

              <label>
                Start date
              </label>

              <input
                type="date"
                value={start}
                onChange={(event) =>
                  setStart(
                    event.target.value
                  )
                }
              />

            </div>


            <div className="backtest-field">

              <label>
                End date
              </label>

              <input
                type="date"
                value={end}
                onChange={(event) =>
                  setEnd(
                    event.target.value
                  )
                }
              />

            </div>

          </div>

        </div>


        {/* =================================================
            CAPITAL / RISK
            ================================================= */}

        <div className="backtest-form-section">

          <div className="backtest-section-heading">

            <div>

              <span className="eyebrow">
                CAPITAL & RISK
              </span>

              <h2>
                Portfolio assumptions
              </h2>

            </div>

          </div>


          <div className="backtest-grid">

            <div className="backtest-field">

              <label>
                Initial capital
              </label>

              <input
                type="number"
                min="1"
                step="1000"
                value={initialCapital}
                onChange={(event) =>
                  setInitialCapital(
                    event.target.value
                  )
                }
              />

            </div>


            <div className="backtest-field">

              <label>
                Risk-free rate
              </label>

              <input
                type="number"
                min="0"
                step="0.001"
                value={riskFreeRate}
                onChange={(event) =>
                  setRiskFreeRate(
                    event.target.value
                  )
                }
              />

              <span className="field-hint">
                0.068 = 6.8%
              </span>

            </div>

          </div>

        </div>


        {error && (
          <div className="backtest-error">

            <strong>
              Backtest unavailable
            </strong>

            <p>
              {error}
            </p>

          </div>
        )}


        <button
          className="backtest-submit"
          type="submit"
          disabled={loading}
        >
          {loading
            ? "Running backtest..."
            : "Run backtest"}
        </button>

      </form>


      {/* =================================================
          RESULTS
          ================================================= */}

      {result && (
        <BacktestResults
          result={result}
        />
      )}

    </section>
  );
}


/* =========================================================
   RESULTS
   ========================================================= */

function BacktestResults({
  result,
}) {

  const metrics =
    result.metrics || {};

  const strategy =
    result.strategy || {};

  const period =
    result.period || {};

  const equity =
    result.equity_curve || [];


  const finalWealth =
    metrics.net_final_wealth;

  const initialCapital =
    result.parameters?.initial_capital;


  const returnClass =
    Number(metrics.total_return) >= 0
      ? "positive"
      : "negative";


  const chartData =
    useMemo(() => {

      if (!equity.length) {
        return null;
      }

      const values =
        equity.map(
          (row) =>
            Number(row.net_equity)
        );

      const grossValues =
        equity.map(
          (row) =>
            Number(row.gross_equity)
        );

      const min =
        Math.min(
          ...values,
          ...grossValues
        );

      const max =
        Math.max(
          ...values,
          ...grossValues
        );

      const range =
        max - min || 1;

      const width = 1000;
      const height = 320;

      const points =
        values.map(
          (value, index) => {

            const x =
              equity.length === 1
                ? width / 2
                : (
                    index /
                    (equity.length - 1)
                  ) *
                  width;

            const y =
              height -
              (
                (value - min) /
                range
              ) *
              (
                height - 30
              ) -
              15;

            return `${x},${y}`;
          }
        );

      const grossPoints =
        grossValues.map(
          (value, index) => {

            const x =
              equity.length === 1
                ? width / 2
                : (
                    index /
                    (equity.length - 1)
                  ) *
                  width;

            const y =
              height -
              (
                (value - min) /
                range
              ) *
              (
                height - 30
              ) -
              15;

            return `${x},${y}`;
          }
        );


      return {
        points:
          points.join(" "),

        grossPoints:
          grossPoints.join(" "),

        min,
        max,
      };

    }, [equity]);


  return (
    <div className="backtest-results">

      {/* =================================================
          RESULT HEADER
          ================================================= */}

      <div className="backtest-results-header">

        <div>

          <span className="eyebrow">
            BACKTEST RESULT
          </span>

          <h2>
            {result.ticker}
          </h2>

          <p>
            {strategy.name}
            {" · "}
            {strategy.fast_ma}
            /
            {strategy.slow_ma}
            {" MA"}
          </p>

        </div>


        <span className="backtest-complete">
          COMPLETE
        </span>

      </div>


      {/* =================================================
          HERO METRICS
          ================================================= */}

      <div className="backtest-hero">

        <div className="backtest-wealth">

          <span>
            FINAL NET WEALTH
          </span>

          <strong>
            {formatMoney(
              finalWealth
            )}
          </strong>

          <small
            className={returnClass}
          >
            {formatPercent(
              metrics.total_return
            )}
          </small>

        </div>


        <div className="backtest-period">

          <span>
            TEST PERIOD
          </span>

          <strong>
            {period.start}
          </strong>

          <small>
            →
            {" "}
            {period.end}
          </small>

        </div>


        <div className="backtest-period">

          <span>
            OBSERVATIONS
          </span>

          <strong>
            {Number(
              period.rows || 0
            ).toLocaleString(
              "en-IN"
            )}
          </strong>

          <small>
            trading days
          </small>

        </div>

      </div>


      {/* =================================================
          METRICS
          ================================================= */}

      <div className="backtest-metrics">

        <BacktestMetric
          label="CAGR"
          value={formatPercent(
            metrics.cagr
          )}
          negative={
            Number(metrics.cagr) < 0
          }
        />

        <BacktestMetric
          label="Sharpe"
          value={formatNumber(
            metrics.sharpe
          )}
          negative={
            Number(metrics.sharpe) < 0
          }
        />

        <BacktestMetric
          label="Volatility"
          value={formatPercent(
            metrics.volatility
          )}
        />

        <BacktestMetric
          label="Max Drawdown"
          value={formatPercent(
            metrics.max_drawdown
          )}
          negative={
            Number(metrics.max_drawdown) < 0
          }
        />

        <BacktestMetric
          label="Trades"
          value={
            metrics.trades
          }
        />

        <BacktestMetric
          label="Transaction Costs"
          value={formatMoney(
            metrics.total_costs
          )}
        />

      </div>


      {/* =================================================
          EQUITY CURVE
          ================================================= */}

      {chartData && (
        <EquityChart
          chartData={chartData}
          initialCapital={
            initialCapital
          }
          finalWealth={
            finalWealth
          }
        />
      )}


      {/* =================================================
          GROSS VS NET
          ================================================= */}

      <div className="backtest-comparison">

        <div>

          <span>
            GROSS FINAL WEALTH
          </span>

          <strong>
            {formatMoney(
              metrics.gross_final_wealth
            )}
          </strong>

        </div>


        <div>

          <span>
            NET FINAL WEALTH
          </span>

          <strong>
            {formatMoney(
              metrics.net_final_wealth
            )}
          </strong>

        </div>


        <div>

          <span>
            COST IMPACT
          </span>

          <strong>
            {formatMoney(
              Number(
                metrics.gross_final_wealth
              ) -
              Number(
                metrics.net_final_wealth
              )
            )}
          </strong>

        </div>

      </div>


      {/* =================================================
          SIGNALS
          ================================================= */}

      <SignalTable
        signals={
          result.signals || []
        }
      />

    </div>
  );
}


/* =========================================================
   METRIC
   ========================================================= */

function BacktestMetric({
  label,
  value,
  negative = false,
}) {
  return (
    <div className="backtest-metric">

      <span>
        {label}
      </span>

      <strong
        className={
          negative
            ? "negative"
            : ""
        }
      >
        {value}
      </strong>

    </div>
  );
}


/* =========================================================
   EQUITY CHART
   ========================================================= */

function EquityChart({
  chartData,
  initialCapital,
  finalWealth,
}) {

  return (
    <div className="equity-card">

      <div className="equity-header">

        <div>

          <span className="eyebrow">
            PERFORMANCE
          </span>

          <h3>
            Equity curve
          </h3>

        </div>

        <div className="equity-legend">

          <span>
            <i className="legend-net" />
            Net
          </span>

          <span>
            <i className="legend-gross" />
            Gross
          </span>

        </div>

      </div>


      <div className="equity-chart">

        <svg
          viewBox="0 0 1000 320"
          preserveAspectRatio="none"
          role="img"
          aria-label="Backtest equity curve"
        >

          <line
            x1="0"
            y1="20"
            x2="1000"
            y2="20"
            className="chart-grid-line"
          />

          <line
            x1="0"
            y1="160"
            x2="1000"
            y2="160"
            className="chart-grid-line"
          />

          <line
            x1="0"
            y1="300"
            x2="1000"
            y2="300"
            className="chart-grid-line"
          />


          <polyline
            points={
              chartData.grossPoints
            }
            className="equity-line gross"
            fill="none"
          />


          <polyline
            points={
              chartData.points
            }
            className="equity-line net"
            fill="none"
          />

        </svg>


        <div className="chart-labels">

          <span>
            {formatMoney(
              chartData.max
            )}
          </span>

          <span>
            Initial{" "}
            {formatMoney(
              initialCapital
            )}
          </span>

          <span>
            Final{" "}
            {formatMoney(
              finalWealth
            )}
          </span>

          <span>
            {formatMoney(
              chartData.min
            )}
          </span>

        </div>

      </div>

    </div>
  );
}


/* =========================================================
   SIGNAL TABLE
   ========================================================= */

function SignalTable({
  signals,
}) {

  const recentSignals =
    [...signals]
      .reverse()
      .slice(0, 20);


  return (
    <div className="signals-card">

      <div className="signals-header">

        <div>

          <span className="eyebrow">
            STRATEGY SIGNALS
          </span>

          <h3>
            Recent positions
          </h3>

        </div>

        <span>
          {signals.length.toLocaleString(
            "en-IN"
          )}{" "}
          observations
        </span>

      </div>


      <div className="signals-table-wrapper">

        <table className="signals-table">

          <thead>

            <tr>
              <th>Date</th>
              <th>Position</th>
              <th>Status</th>
            </tr>

          </thead>


          <tbody>

            {recentSignals.map(
              (row) => {

                const position =
                  Number(
                    row.position
                  );

                const active =
                  position > 0;

                return (
                  <tr
                    key={
                      row.date
                    }
                  >

                    <td>
                      {row.date}
                    </td>

                    <td>
                      {position.toFixed(
                        2
                      )}
                    </td>

                    <td>

                      <span
                        className={
                          active
                            ? "position-badge active"
                            : "position-badge"
                        }
                      >
                        {active
                          ? "LONG"
                          : "FLAT"}
                      </span>

                    </td>

                  </tr>
                );
              }
            )}

          </tbody>

        </table>

      </div>

    </div>
  );
}