import { useState } from "react";
import { runBlackScholes } from "../api/quant";
import "./BlackScholes.css";

function number(value, digits = 4) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "—";
}

function price(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(4);
}

export default function BlackScholes() {
  const [spot, setSpot] = useState(100);
  const [strike, setStrike] = useState(100);
  const [timeToExpiry, setTimeToExpiry] = useState(1);
  const [volatility, setVolatility] = useState(0.20);
  const [riskFreeRate, setRiskFreeRate] = useState(0.05);
  const [dividendYield, setDividendYield] = useState(0.02);
  const [optionType, setOptionType] = useState("call");
  const [marketPrice, setMarketPrice] = useState("");

  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setResult(null);

    if (Number(spot) <= 0 || Number(strike) <= 0) {
      setError("Spot and strike must be greater than zero.");
      return;
    }

    if (Number(timeToExpiry) <= 0) {
      setError("Time to expiry must be greater than zero.");
      return;
    }

    if (Number(volatility) <= 0) {
      setError("Volatility must be greater than zero.");
      return;
    }

    setLoading(true);

    try {
      const data = await runBlackScholes({
        spot,
        strike,
        timeToExpiry,
        volatility,
        riskFreeRate,
        dividendYield,
        optionType,
        marketPrice,
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
            "Unable to calculate Black-Scholes value."
        );
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="bs-page">
      <header className="bs-header">
        <div className="bs-eyebrow">
          QUANT PLATFORM / DERIVATIVES
        </div>

        <div className="bs-header-row">
          <div>
            <h1>Black-Scholes</h1>
            <p>
              European option valuation with pricing, Greeks,
              implied volatility and put-call parity diagnostics.
            </p>
          </div>

          <div className="bs-status">
            <span />
            EUROPEAN OPTIONS
          </div>
        </div>
      </header>

      <div className="bs-content">
        <form className="bs-form" onSubmit={handleSubmit}>
          <div className="bs-section-label">
            OPTION PARAMETERS
          </div>

          <div className="bs-grid">
            <Field label="Spot price">
              <input
                type="number"
                min="0"
                step="0.01"
                value={spot}
                onChange={(e) => setSpot(e.target.value)}
              />
            </Field>

            <Field label="Strike price">
              <input
                type="number"
                min="0"
                step="0.01"
                value={strike}
                onChange={(e) => setStrike(e.target.value)}
              />
            </Field>

            <Field label="Time to expiry" hint="Years">
              <input
                type="number"
                min="0"
                step="0.01"
                value={timeToExpiry}
                onChange={(e) => setTimeToExpiry(e.target.value)}
              />
            </Field>

            <Field label="Volatility" hint="0.20 = 20%">
              <input
                type="number"
                min="0"
                step="0.001"
                value={volatility}
                onChange={(e) => setVolatility(e.target.value)}
              />
            </Field>

            <Field label="Risk-free rate" hint="0.05 = 5%">
              <input
                type="number"
                step="0.001"
                value={riskFreeRate}
                onChange={(e) => setRiskFreeRate(e.target.value)}
              />
            </Field>

            <Field label="Dividend yield" hint="0.02 = 2%">
              <input
                type="number"
                min="0"
                step="0.001"
                value={dividendYield}
                onChange={(e) => setDividendYield(e.target.value)}
              />
            </Field>
          </div>

          <div className="bs-option-row">
            <div className="bs-type">
              <span>OPTION TYPE</span>

              <div className="bs-toggle">
                <button
                  type="button"
                  className={optionType === "call" ? "active" : ""}
                  onClick={() => setOptionType("call")}
                >
                  CALL
                </button>

                <button
                  type="button"
                  className={optionType === "put" ? "active" : ""}
                  onClick={() => setOptionType("put")}
                >
                  PUT
                </button>
              </div>
            </div>

            <Field
              label="Market price"
              hint="Optional — enables implied volatility"
            >
              <input
                type="number"
                min="0"
                step="0.0001"
                value={marketPrice}
                onChange={(e) => setMarketPrice(e.target.value)}
                placeholder="Optional"
              />
            </Field>
          </div>

          {error && (
            <div className="bs-error">
              <strong>CALCULATION UNAVAILABLE</strong>
              <span>{error}</span>
            </div>
          )}

          <button
            className="bs-submit"
            type="submit"
            disabled={loading}
          >
            {loading ? "Calculating..." : "Calculate option value"}
          </button>
        </form>

        {result && <BlackScholesResults result={result} />}
      </div>
    </section>
  );
}

function Field({ label, hint, children }) {
  return (
    <div className="bs-field">
      <label>{label}</label>
      {children}
      {hint && <small>{hint}</small>}
    </div>
  );
}

function BlackScholesResults({ result }) {
  const inputs = result.inputs || {};
  const prices = result.price || {};
  const greeks = result.greeks || {};
  const parity = result.put_call_parity || {};

  return (
    <div className="bs-results">
      <div className="bs-results-header">
        <div>
          <div className="bs-eyebrow">VALUATION RESULT</div>
          <h2>
            {String(inputs.option_type || "call").toUpperCase()} OPTION
          </h2>
        </div>

        <div className="bs-complete">
          <span />
          COMPLETE
        </div>
      </div>

      <div className="bs-price-hero">
        <div>
          <span>SELECTED OPTION VALUE</span>
          <strong>{price(prices.option)}</strong>
        </div>

        <div className="bs-price-side">
          <Stat label="Call" value={price(prices.call)} />
          <Stat label="Put" value={price(prices.put)} />
        </div>
      </div>

      <div className="bs-greeks">
        <Greek label="Delta" value={number(greeks.delta)} />
        <Greek label="Gamma" value={number(greeks.gamma)} />
        <Greek label="Vega" value={number(greeks.vega)} />
        <Greek label="Theta" value={number(greeks.theta)} />
        <Greek label="Rho" value={number(greeks.rho)} />
      </div>

      <div className="bs-diagnostics">
        <div className="bs-diagnostic-main">
          <div className="bs-eyebrow">IMPLIED VOLATILITY</div>
          <h3>
            {greeks.implied_volatility !== null &&
            greeks.implied_volatility !== undefined
              ? `${(Number(greeks.implied_volatility) * 100).toFixed(2)}%`
              : result.implied_volatility !== null &&
                  result.implied_volatility !== undefined
                ? `${(Number(result.implied_volatility) * 100).toFixed(2)}%`
                : "Not requested"}
          </h3>
          <p>
            Provide a market option price to solve for the
            volatility implied by that price.
          </p>
        </div>

        <div className="bs-parity">
          <div className="bs-eyebrow">PUT-CALL PARITY</div>

          <div className="bs-parity-status">
            <span className={parity.parity_holds ? "pass" : "fail"} />
            {parity.parity_holds ? "HOLDS" : "CHECK"}
          </div>

          <div className="bs-parity-grid">
            <Stat
              label="Forward"
              value={number(parity.forward)}
            />
            <Stat
              label="Discrepancy"
              value={number(parity.discrepancy)}
            />
          </div>
        </div>
      </div>

      <div className="bs-input-summary">
        <Stat label="Spot" value={price(inputs.spot)} />
        <Stat label="Strike" value={price(inputs.strike)} />
        <Stat
          label="Expiry"
          value={`${number(inputs.time_to_expiry, 2)} yr`}
        />
        <Stat
          label="Volatility"
          value={`${(Number(inputs.volatility) * 100).toFixed(2)}%`}
        />
        <Stat
          label="Risk-free"
          value={`${(Number(inputs.risk_free_rate) * 100).toFixed(2)}%`}
        />
        <Stat
          label="Dividend"
          value={`${(Number(inputs.dividend_yield) * 100).toFixed(2)}%`}
        />
      </div>
    </div>
  );
}

function Greek({ label, value }) {
  return (
    <div className="bs-greek">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="bs-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}