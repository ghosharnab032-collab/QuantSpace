import { useState } from "react";
import { optimizePortfolio } from "../api/quant";
import "./PortfolioOptimizer.css";

function formatPercent(value) {
  const n = Number(value);
  return Number.isFinite(n) ? `${(n * 100).toFixed(2)}%` : "—";
}

function formatNumber(value, digits = 2) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "—";
}

function formatDate(value) {
  return value || "—";
}

export default function PortfolioOptimizer() {
  const [tickers, setTickers] = useState(["RELIANCE", "TCS", "INFY"]);
  const [start, setStart] = useState("2021-01-01");
  const [end, setEnd] = useState("2026-08-19");
  const [riskFreeRate, setRiskFreeRate] = useState("0.068");
  const [maxWeight, setMaxWeight] = useState("0.60");
  const [transactionCostBps, setTransactionCostBps] = useState("10");
  const [lookbackMonths, setLookbackMonths] = useState("24");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function updateTicker(index, value) {
    setTickers((current) =>
      current.map((ticker, i) =>
        i === index ? value.toUpperCase() : ticker
      )
    );
  }

  function addTicker() {
    setTickers((current) => [...current, ""]);
  }

  function removeTicker(index) {
    setTickers((current) => current.filter((_, i) => i !== index));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setResult(null);

    const cleaned = tickers
      .map((ticker) => ticker.trim().toUpperCase())
      .filter(Boolean);

    if (cleaned.length < 2) {
      setError("Add at least two assets.");
      return;
    }

    if (new Set(cleaned).size !== cleaned.length) {
      setError("Duplicate tickers are not allowed.");
      return;
    }

    if (start > end) {
      setError("Start date cannot be after end date.");
      return;
    }

    setLoading(true);

    try {
      const data = await optimizePortfolio({
        tickers: cleaned,
        start,
        end,
        riskFreeRate,
        maxWeight,
        transactionCostBps,
        lookbackMonths,
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
            "Unable to optimize portfolio."
        );
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="po-page">
      <header className="po-header">
        <div className="po-eyebrow">QUANT PLATFORM / OPTIMIZATION</div>

        <div className="po-header-row">
          <div>
            <h1>Portfolio Optimizer</h1>
            <p>
              Find a maximum-Sharpe allocation using aligned monthly
              market data and rolling historical optimization.
            </p>
          </div>

          <div className="po-status">
            <span />
            MAXIMUM SHARPE
          </div>
        </div>
      </header>

      <div className="po-content">
        <form className="po-form" onSubmit={handleSubmit}>
          <div className="po-section-label">OPTIMIZATION PARAMETERS</div>

          <div className="po-assets">
            <div className="po-subheading">
              <div>
                <span>INVESTMENT UNIVERSE</span>
                <h2>Assets</h2>
              </div>

              <button
                type="button"
                className="po-secondary"
                onClick={addTicker}
              >
                + Add asset
              </button>
            </div>

            <div className="po-ticker-grid">
              {tickers.map((ticker, index) => (
                <div className="po-ticker" key={index}>
                  <span>{String(index + 1).padStart(2, "0")}</span>

                  <input
                    value={ticker}
                    onChange={(event) =>
                      updateTicker(index, event.target.value)
                    }
                    placeholder="RELIANCE"
                  />

                  {tickers.length > 2 && (
                    <button
                      type="button"
                      onClick={() => removeTicker(index)}
                      aria-label={`Remove asset ${index + 1}`}
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="po-grid po-grid-two">
            <Field label="Start date">
              <input
                type="date"
                value={start}
                onChange={(event) => setStart(event.target.value)}
              />
            </Field>

            <Field label="End date">
              <input
                type="date"
                value={end}
                onChange={(event) => setEnd(event.target.value)}
              />
            </Field>
          </div>

          <div className="po-grid">
            <Field label="Risk-free rate" hint="0.068 = 6.8%">
              <input
                type="number"
                step="0.001"
                min="0"
                value={riskFreeRate}
                onChange={(event) =>
                  setRiskFreeRate(event.target.value)
                }
              />
            </Field>

            <Field label="Maximum weight" hint="0.60 = 60%">
              <input
                type="number"
                step="0.01"
                min="0.01"
                max="1"
                value={maxWeight}
                onChange={(event) =>
                  setMaxWeight(event.target.value)
                }
              />
            </Field>

            <Field label="Transaction cost" hint="Basis points">
              <input
                type="number"
                step="1"
                min="0"
                value={transactionCostBps}
                onChange={(event) =>
                  setTransactionCostBps(event.target.value)
                }
              />
            </Field>

            <Field label="Lookback period" hint="Months">
              <input
                type="number"
                min="2"
                value={lookbackMonths}
                onChange={(event) =>
                  setLookbackMonths(event.target.value)
                }
              />
            </Field>
          </div>

          {error && (
            <div className="po-error">
              <strong>OPTIMIZATION UNAVAILABLE</strong>
              <span>{error}</span>
            </div>
          )}

          <button
            className="po-submit"
            type="submit"
            disabled={loading}
          >
            {loading ? "Optimizing portfolio..." : "Run optimizer"}
          </button>
        </form>

        {result && <OptimizerResults result={result} />}
      </div>
    </section>
  );
}

function Field({ label, hint, children }) {
  return (
    <div className="po-field">
      <label>{label}</label>
      {children}
      {hint && <small>{hint}</small>}
    </div>
  );
}

function OptimizerResults({ result }) {
  const weights = result.final_weights || {};
  const assets = result.assets || Object.keys(weights);
  const optimizer = result.optimizer || {};
  const benchmark = result.benchmark || {};
  const parameters = result.parameters || {};
  const observations = result.observations || {};

  return (
    <div className="po-results">
      <div className="po-results-header">
        <div>
          <div className="po-eyebrow">OPTIMIZATION RESULT</div>
          <h2>Optimal allocation</h2>
        </div>

        <div className="po-complete">
          <span />
          COMPLETE
        </div>
      </div>

      <div className="po-allocation-card">
        <div className="po-card-heading">
          <div>
            <span>FINAL WEIGHTS</span>
            <h3>Portfolio allocation</h3>
          </div>

          <span>{assets.length} assets</span>
        </div>

        <div className="po-allocation-list">
          {assets.map((ticker) => {
            const weight = Number(weights[ticker]) || 0;
            const percentage = Math.max(0, Math.min(100, weight * 100));

            return (
              <div className="po-allocation-row" key={ticker}>
                <div className="po-allocation-label">
                  <strong>{ticker}</strong>
                  <span>{percentage.toFixed(2)}%</span>
                </div>

                <div className="po-allocation-track">
                  <div
                    className="po-allocation-fill"
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="po-metric-comparison">
        <MetricColumn
          title="OPTIMIZER"
          cagr={optimizer.cagr}
          volatility={optimizer.volatility}
          sharpe={optimizer.sharpe}
          drawdown={optimizer.max_drawdown}
          emphasis
        />

        <MetricColumn
          title="EQUAL-WEIGHT BENCHMARK"
          cagr={benchmark.cagr}
          volatility={benchmark.volatility}
          sharpe={benchmark.sharpe}
          drawdown={benchmark.max_drawdown}
        />
      </div>

      <div className="po-run-info">
        <Stat
          label="Risk-free rate"
          value={formatPercent(parameters.risk_free_rate)}
        />
        <Stat
          label="Maximum weight"
          value={formatPercent(parameters.max_weight)}
        />
        <Stat
          label="Transaction cost"
          value={`${formatNumber(parameters.transaction_cost_bps, 0)} bps`}
        />
        <Stat
          label="Lookback"
          value={`${formatNumber(parameters.lookback_months, 0)} months`}
        />
        <Stat
          label="Monthly observations"
          value={Number(observations.monthly_returns || 0).toLocaleString("en-IN")}
        />
        <Stat
          label="Backtest months"
          value={Number(observations.backtest_months || 0).toLocaleString("en-IN")}
        />
      </div>
    </div>
  );
}

function MetricColumn({
  title,
  cagr,
  volatility,
  sharpe,
  drawdown,
  emphasis = false,
}) {
  return (
    <div className={`po-metric-column ${emphasis ? "emphasis" : ""}`}>
      <div className="po-metric-title">{title}</div>

      <Metric label="CAGR" value={formatPercent(cagr)} />
      <Metric
        label="Volatility"
        value={formatPercent(volatility)}
      />
      <Metric label="Sharpe" value={formatNumber(sharpe)} />
      <Metric
        label="Max drawdown"
        value={formatPercent(drawdown)}
      />
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="po-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="po-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}