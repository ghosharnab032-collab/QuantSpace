import { useState } from "react";
import { runBacktest } from "../api/quant";
import "./Backtester.css";

function n(value) {
  const x = Number(value);
  return Number.isFinite(x) ? x : null;
}

function money(value) {
  const x = n(value);
  return x === null
    ? "—"
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
      }).format(x);
}

function pct(value) {
  const x = n(value);
  return x === null ? "—" : `${(x * 100).toFixed(2)}%`;
}

function num(value, digits = 2) {
  const x = n(value);
  return x === null ? "—" : x.toFixed(digits);
}

export default function Backtester() {
  const [ticker, setTicker] = useState("RELIANCE");
  const [start, setStart] = useState("2021-01-01");
  const [end, setEnd] = useState("2026-08-19");
  const [fastMa, setFastMa] = useState(20);
  const [slowMa, setSlowMa] = useState(50);
  const [initialCapital, setInitialCapital] = useState(100000);
  const [riskFreeRate, setRiskFreeRate] = useState("0.068");

  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setResult(null);

    if (Number(fastMa) >= Number(slowMa)) {
      setError("Fast moving average must be smaller than slow moving average.");
      return;
    }

    if (start > end) {
      setError("Start date cannot be after end date.");
      return;
    }

    setLoading(true);

    try {
      const data = await runBacktest({
        ticker,
        start,
        end,
        fastMa,
        slowMa,
        initialCapital,
        riskFreeRate,
      });

      setResult(data);
    } catch (err) {
      const detail = err?.response?.data?.detail;

      if (Array.isArray(detail)) {
        setError(detail.map((item) => item.msg).join(", "));
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
    <section className="bt-page">
      <header className="bt-header">
        <div className="bt-eyebrow">
          QUANT PLATFORM / STRATEGY RESEARCH
        </div>

        <div className="bt-header-row">
          <div>
            <h1>Backtester</h1>
            <p>
              Test a moving-average strategy against historical
              NSE equity data with India-specific delivery costs.
            </p>
          </div>

          <div className="bt-status">
            <span />
            MOVING AVERAGE
          </div>
        </div>
      </header>

      <div className="bt-content">
        <form className="bt-form" onSubmit={handleSubmit}>
          <div className="bt-section-label">
            STRATEGY PARAMETERS
          </div>

          <div className="bt-grid bt-grid-top">
            <Field label="Ticker">
              <input
                value={ticker}
                onChange={(e) =>
                  setTicker(e.target.value.toUpperCase())
                }
                placeholder="RELIANCE"
              />
            </Field>

            <Field label="Start date">
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </Field>

            <Field label="End date">
              <input
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </Field>
          </div>

          <div className="bt-grid">
            <Field label="Fast MA" hint="Trading days">
              <input
                type="number"
                min="1"
                value={fastMa}
                onChange={(e) => setFastMa(e.target.value)}
              />
            </Field>

            <Field label="Slow MA" hint="Trading days">
              <input
                type="number"
                min="2"
                value={slowMa}
                onChange={(e) => setSlowMa(e.target.value)}
              />
            </Field>

            <Field label="Initial capital">
              <input
                type="number"
                min="1"
                value={initialCapital}
                onChange={(e) =>
                  setInitialCapital(e.target.value)
                }
              />
            </Field>

            <Field label="Risk-free rate" hint="0.068 = 6.8%">
              <input
                type="number"
                min="0"
                step="0.001"
                value={riskFreeRate}
                onChange={(e) =>
                  setRiskFreeRate(e.target.value)
                }
              />
            </Field>
          </div>

          <div className="bt-execution-note">
            <div>
              <span>EXECUTION MODEL</span>
              <strong>Signal at close → execute next open</strong>
            </div>

            <div>
              <span>POSITION</span>
              <strong>Long / Flat</strong>
            </div>

            <div>
              <span>COST MODEL</span>
              <strong>India equity delivery</strong>
            </div>
          </div>

          {error && (
            <div className="bt-error">
              <strong>BACKTEST UNAVAILABLE</strong>
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            className="bt-submit"
            disabled={loading}
          >
            {loading ? "Running backtest..." : "Run backtest"}
          </button>
        </form>

        {result && <BacktestResults result={result} />}
      </div>
    </section>
  );
}

function Field({ label, hint, children }) {
  return (
    <div className="bt-field">
      <label>{label}</label>
      {children}
      {hint && <small>{hint}</small>}
    </div>
  );
}

function BacktestResults({ result }) {
  const strategy = result.strategy || {};
  const parameters = result.parameters || {};
  const period = result.period || {};
  const metrics = result.metrics || {};
  const curve = Array.isArray(result.equity_curve)
    ? result.equity_curve
    : [];

  return (
    <div className="bt-results">
      <div className="bt-results-header">
        <div>
          <div className="bt-eyebrow">BACKTEST RESULT</div>
          <h2>{result.ticker}</h2>
          <p>
            {period.start} — {period.end} ·{" "}
            {Number(period.rows || 0).toLocaleString("en-IN")} sessions
          </p>
        </div>

        <div className="bt-complete">
          <span />
          COMPLETE
        </div>
      </div>

      <div className="bt-strategy-strip">
        <Stat label="Strategy" value={strategy.name || "—"} />
        <Stat
          label="Fast / Slow"
          value={`${strategy.fast_ma ?? "—"} / ${strategy.slow_ma ?? "—"}`}
        />
        <Stat
          label="Execution"
          value={strategy.execution || "—"}
        />
        <Stat
          label="Position"
          value={strategy.position_type || "—"}
        />
      </div>

      <div className="bt-metrics">
        <Metric label="Total return" value={pct(metrics.total_return)} />
        <Metric label="CAGR" value={pct(metrics.cagr)} />
        <Metric label="Volatility" value={pct(metrics.volatility)} />
        <Metric label="Sharpe" value={num(metrics.sharpe)} />
        <Metric label="Max drawdown" value={pct(metrics.max_drawdown)} />
        <Metric label="Trades" value={num(metrics.trades, 0)} />
        <Metric label="Total costs" value={money(metrics.total_costs)} />
        <Metric
          label="Net final wealth"
          value={money(metrics.net_final_wealth)}
        />
      </div>

      <EquityChart data={curve} />

      <div className="bt-capital">
        <Stat
          label="Initial capital"
          value={money(parameters.initial_capital)}
        />
        <Stat
          label="Gross final wealth"
          value={money(metrics.gross_final_wealth)}
        />
        <Stat
          label="Net final wealth"
          value={money(metrics.net_final_wealth)}
        />
        <Stat
          label="Risk-free rate"
          value={pct(parameters.risk_free_rate)}
        />
      </div>

      <div className="bt-costs">
        <div className="bt-cost-heading">
          <div className="bt-eyebrow">INDIA DELIVERY COST MODEL</div>
          <h3>Transaction assumptions</h3>
        </div>

        <div className="bt-cost-grid">
          <Stat label="STT" value={pct(parameters.stt)} />
          <Stat
            label="Stamp duty"
            value={pct(parameters.stamp_buy)}
          />
          <Stat label="SEBI" value={pct(parameters.sebi)} />
          <Stat
            label="Brokerage"
            value={pct(parameters.brokerage)}
          />
          <Stat
            label="Exchange"
            value={pct(parameters.exchange_service)}
          />
          <Stat label="GST" value={pct(parameters.gst)} />
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="bt-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="bt-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EquityChart({ data }) {
  const [hoverIndex, setHoverIndex] = useState(null);

  if (!data.length) {
    return (
      <div className="bt-chart-empty">
        No equity-curve observations returned.
      </div>
    );
  }

  const width = 1200;
  const height = 470;
  const left = 76;
  const right = 30;
  const top = 28;
  const bottom = 54;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;

  const values = data
    .map((row) => n(row.net_equity))
    .filter((value) => value !== null);

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || Math.max(maxValue * 0.02, 1);
  const pad = range * 0.08;
  const min = minValue - pad;
  const max = maxValue + pad;

  const xFor = (i) =>
    left +
    (i / Math.max(data.length - 1, 1)) * plotWidth;

  const yFor = (value) =>
    top + ((max - value) / (max - min)) * plotHeight;

  const points = data
    .map((row, i) => {
      const value = n(row.net_equity);
      return value === null
        ? null
        : `${xFor(i)},${yFor(value)}`;
    })
    .filter(Boolean)
    .join(" ");

  const ticks = Array.from({ length: 5 }, (_, i) =>
    max - ((max - min) * i) / 4
  );

  const xCount = Math.min(6, data.length);
  const xTicks = Array.from({ length: xCount }, (_, i) => {
    const index =
      xCount === 1
        ? 0
        : Math.round(
            (i / (xCount - 1)) * (data.length - 1)
          );

    return {
      index,
      row: data[index],
    };
  });

  const hovered =
    hoverIndex === null
      ? data[data.length - 1]
      : data[hoverIndex];

  const hoveredValue = n(hovered?.net_equity);
  const hoveredX =
    hoverIndex === null ? null : xFor(hoverIndex);
  const hoveredY =
    hoveredValue === null ? null : yFor(hoveredValue);

  return (
    <div className="bt-chart">
      <div className="bt-chart-header">
        <div>
          <span>NET EQUITY</span>
          <strong>{money(hoveredValue)}</strong>
        </div>

        <div>
          <span>{hovered?.date || "—"}</span>
        </div>
      </div>

      <div className="bt-svg-wrap">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          width="100%"
          height={height}
          role="img"
          aria-label="Backtest equity curve"
          onMouseLeave={() => setHoverIndex(null)}
        >
          {ticks.map((value, i) => {
            const y = yFor(value);

            return (
              <g key={`grid-${i}`}>
                <line
                  x1={left}
                  x2={width - right}
                  y1={y}
                  y2={y}
                  className="bt-grid-line"
                />
                <text
                  x={left - 12}
                  y={y + 4}
                  textAnchor="end"
                  className="bt-axis"
                >
                  {Math.round(value).toLocaleString("en-IN")}
                </text>
              </g>
            );
          })}

          <polyline
            points={points}
            fill="none"
            className="bt-equity-line"
          />

          {data.map((row, i) => {
            const slot = plotWidth / Math.max(data.length, 1);

            return (
              <rect
                key={`hit-${row.date}-${i}`}
                x={xFor(i) - Math.max(slot / 2, 3)}
                y={top}
                width={Math.max(slot, 6)}
                height={plotHeight}
                fill="transparent"
                onMouseEnter={() => setHoverIndex(i)}
              />
            );
          })}

          {hoverIndex !== null &&
            hoveredX !== null &&
            hoveredY !== null && (
              <>
                <line
                  x1={hoveredX}
                  x2={hoveredX}
                  y1={top}
                  y2={height - bottom}
                  className="bt-crosshair"
                />
                <circle
                  cx={hoveredX}
                  cy={hoveredY}
                  r="5"
                  className="bt-dot"
                />
              </>
            )}

          {xTicks.map(({ index, row }) => (
            <text
              key={`date-${row.date}-${index}`}
              x={xFor(index)}
              y={height - 18}
              textAnchor="middle"
              className="bt-axis"
            >
              {row.date}
            </text>
          ))}
        </svg>
      </div>

      <div className="bt-chart-footer">
        <span>
          {data.length.toLocaleString("en-IN")} trading sessions
        </span>
        <span>
          Net equity · after transaction costs
        </span>
      </div>
    </div>
  );
}