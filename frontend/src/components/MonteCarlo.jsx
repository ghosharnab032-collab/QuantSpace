import { useEffect, useState } from "react";

import { runMonteCarlo } from "../api/quant";
import {
  createPaymentOrder,
  verifyPayment,
} from "../api/payments";
import { getEntitlement } from "../api/entitlements";

import "./MonteCarlo.css";

const MONTE_CARLO_PRICE = 49900; // ₹499 in paise

export default function MonteCarlo() {
  const [tickers, setTickers] = useState(
    "RELIANCE, TCS, INFY"
  );

  const [initialAmount, setInitialAmount] =
    useState(100000);

  const [years, setYears] = useState(10);

  const [simulations, setSimulations] =
    useState(10000);

  const [strategy, setStrategy] =
    useState("rebalance");

  const [annualDrag, setAnnualDrag] =
    useState(0);

  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const [loading, setLoading] =
    useState(false);

  const [unlocking, setUnlocking] =
    useState(false);

  const [checkingEntitlement, setCheckingEntitlement] =
    useState(true);

  const [unlocked, setUnlocked] =
    useState(false);

  // ==========================================================
  // CHECK ENTITLEMENT
  // ==========================================================

  useEffect(() => {
    let mounted = true;

    async function checkEntitlement() {
      setCheckingEntitlement(true);
      setError("");

      try {
        const entitlement =
          await getEntitlement("monte_carlo");

        if (mounted) {
          setUnlocked(
            Boolean(entitlement?.active)
          );
        }
      } catch (err) {
        if (!mounted) return;

        setUnlocked(false);

        const status =
          err?.response?.status;

        const detail =
          err?.response?.data?.detail;

        if (status === 401) {
          setError(
            "Please log in to access Monte Carlo."
          );
        } else if (status === 403) {
          setError(
            "Monte Carlo requires an active entitlement."
          );
        } else {
          setError(
            detail ||
              err?.message ||
              "Unable to check Monte Carlo access."
          );
        }
      } finally {
        if (mounted) {
          setCheckingEntitlement(false);
        }
      }
    }

    checkEntitlement();

    return () => {
      mounted = false;
    };
  }, []);

  // ==========================================================
  // BUILD PAYLOAD
  // ==========================================================

  function buildPayload() {
    const tickerList = tickers
      .split(",")
      .map((ticker) =>
        ticker.trim().toUpperCase()
      )
      .filter(Boolean);

    if (tickerList.length === 0) {
      throw new Error(
        "Enter at least one ticker."
      );
    }

    const amount = Number(initialAmount);
    const horizon = Number(years);
    const simCount = Number(simulations);
    const drag = Number(annualDrag);

    if (
      !Number.isFinite(amount) ||
      amount <= 0
    ) {
      throw new Error(
        "Initial capital must be greater than zero."
      );
    }

    if (
      !Number.isFinite(horizon) ||
      horizon <= 0
    ) {
      throw new Error(
        "Horizon must be greater than zero."
      );
    }

    if (
      !Number.isFinite(simCount) ||
      simCount <= 0
    ) {
      throw new Error(
        "Simulations must be greater than zero."
      );
    }

    if (
      !Number.isFinite(drag) ||
      drag < 0 ||
      drag >= 1
    ) {
      throw new Error(
        "Annual drag must be between 0 and 1."
      );
    }

    return {
      tickers: tickerList,

      // Exact backend schema names
      initial_amount: amount,

      years: horizon,

      simulations: simCount,

      strategy,

      annual_drag: drag,
    };
  }

  // ==========================================================
  // RUN SIMULATION
  // ==========================================================

  async function executeSimulation() {
    setError("");
    setResult(null);
    setLoading(true);

    try {
      const payload = buildPayload();

      console.log(
        "[MONTE CARLO REQUEST]",
        payload
      );

      const data =
        await runMonteCarlo(payload);

      console.log(
        "[MONTE CARLO RESPONSE]",
        data
      );

      setResult(data);

      return true;
    } catch (err) {
      console.error(
        "[MONTE CARLO ERROR]",
        err
      );

      const status =
        err?.response?.status;

      const detail =
        err?.response?.data?.detail;

      if (status === 401) {
        setError(
          "Your session has expired. Please log in again."
        );
      } else if (status === 403) {
        setUnlocked(false);

        setError(
          detail ||
            "Monte Carlo requires an active entitlement."
        );
      } else if (status === 422) {
        if (Array.isArray(detail)) {
          setError(
            detail
              .map((item) => {
                const location =
                  Array.isArray(item.loc)
                    ? item.loc.join(".")
                    : "";

                return location
                  ? `${location}: ${item.msg}`
                  : item.msg;
              })
              .join(" | ")
          );
        } else {
          setError(
            detail ||
              "Invalid Monte Carlo request."
          );
        }
      } else {
        setError(
          detail ||
            err?.message ||
            "Monte Carlo simulation failed."
        );
      }

      return false;
    } finally {
      setLoading(false);
    }
  }

  // ==========================================================
  // FORM SUBMIT
  // ==========================================================

  async function handleSubmit(event) {
    event.preventDefault();

    if (!unlocked) {
      setError(
        "Unlock Monte Carlo before running a simulation."
      );
      return;
    }

    await executeSimulation();
  }

  // ==========================================================
  // RAZORPAY UNLOCK
  // ==========================================================

  async function handleUnlock() {
    setError("");
    setResult(null);
    setUnlocking(true);

    try {
      if (
        typeof window.Razorpay !==
        "function"
      ) {
        throw new Error(
          "Razorpay Checkout failed to load. Please refresh the page."
        );
      }

      // ------------------------------------------------------
      // CREATE ORDER
      // ------------------------------------------------------

      const order =
        await createPaymentOrder({
          product: "monte_carlo",

          // Backend expects paise.
          // ₹499 = 49900 paise.
          amount: MONTE_CARLO_PRICE,
        });

      if (!order?.order_id) {
        throw new Error(
          "Payment order was not created."
        );
      }

      if (!order?.key_id) {
        throw new Error(
          "Razorpay key was not returned by the server."
        );
      }

      // ------------------------------------------------------
      // OPEN RAZORPAY CHECKOUT
      // ------------------------------------------------------

      await new Promise(
        (resolve, reject) => {
          let settled = false;

          function resolveOnce() {
            if (settled) return;

            settled = true;
            resolve();
          }

          function rejectOnce(error) {
            if (settled) return;

            settled = true;
            reject(error);
          }

          const options = {
            key: order.key_id,

            amount:
              order.amount ||
              MONTE_CARLO_PRICE,

            currency:
              order.currency || "INR",

            name: "Quant Space",

            description:
              "Monte Carlo Pro",

            order_id:
              order.order_id,

            handler: async function (
              response
            ) {
              try {
                console.log(
                  "[RAZORPAY PAYMENT]",
                  response
                );

                const verification =
                  await verifyPayment({
                    razorpay_order_id:
                      response.razorpay_order_id,

                    razorpay_payment_id:
                      response.razorpay_payment_id,

                    razorpay_signature:
                      response.razorpay_signature,
                  });

                console.log(
                  "[PAYMENT VERIFICATION]",
                  verification
                );

                if (
                  verification?.verified &&
                  verification?.entitlement ===
                    "monte_carlo"
                ) {
                  resolveOnce();
                  return;
                }

                rejectOnce(
                  new Error(
                    "Payment was received but Monte Carlo entitlement verification failed."
                  )
                );
              } catch (err) {
                rejectOnce(err);
              }
            },

            modal: {
              ondismiss: () => {
                rejectOnce(
                  new Error(
                    "Payment cancelled."
                  )
                );
              },
            },

            theme: {
              color: "#111113",
            },
          };

          const razorpay =
            new window.Razorpay(
              options
            );

          razorpay.on(
            "payment.failed",
            (response) => {
              rejectOnce(
                new Error(
                  response?.error
                    ?.description ||
                    "Payment failed."
                )
              );
            }
          );

          razorpay.open();
        }
      );

      // ------------------------------------------------------
      // CONFIRM ENTITLEMENT FROM BACKEND
      // ------------------------------------------------------

      const entitlement =
        await getEntitlement(
          "monte_carlo"
        );

      if (!entitlement?.active) {
        throw new Error(
          "Payment was verified, but Monte Carlo access is not active yet."
        );
      }

      setUnlocked(true);

      // ------------------------------------------------------
      // AUTOMATICALLY RUN SIMULATION
      // ------------------------------------------------------

      await executeSimulation();
    } catch (err) {
      console.error(
        "[MONTE CARLO UNLOCK ERROR]",
        err
      );

      const detail =
        err?.response?.data?.detail;

      setError(
        detail ||
          err?.message ||
          "Unable to unlock Monte Carlo."
      );
    } finally {
      setUnlocking(false);
    }
  }

  // ==========================================================
  // CHECKING STATE
  // ==========================================================

  if (checkingEntitlement) {
    return (
      <section className="mc-page">
        <header className="mc-header">
          <div className="mc-eyebrow">
            QUANT SPACE / SIMULATION
          </div>

          <div className="mc-header-row">
            <div>
              <h1>Monte Carlo</h1>

              <p>
                Model a range of potential
                portfolio outcomes using
                historical market behavior.
              </p>
            </div>

            <div className="mc-status">
              <span />
              CHECKING ACCESS
            </div>
          </div>
        </header>

        <div className="mc-content">
          <div className="mc-ready">
            <span>CHECKING</span>

            Checking your Monte Carlo
            entitlement...
          </div>
        </div>
      </section>
    );
  }

  // ==========================================================
  // MAIN UI
  // ==========================================================

  return (
    <section className="mc-page">
      <header className="mc-header">
        <div className="mc-eyebrow">
          QUANT SPACE / SIMULATION
        </div>

        <div className="mc-header-row">
          <div>
            <h1>Monte Carlo</h1>

            <p>
              Model a range of potential
              portfolio outcomes using
              historical market behavior.
            </p>
          </div>

          <div className="mc-status">
            <span />

            {unlocked
              ? "PRO UNLOCKED"
              : "PRO TOOL"}
          </div>
        </div>
      </header>

      <div className="mc-content">
        <form
          className="mc-query"
          onSubmit={handleSubmit}
        >
          <div className="mc-query-label">
            SIMULATION PARAMETERS
          </div>

          {/* ==================================================
              TICKERS
              ================================================== */}

          <div className="mc-grid mc-grid-top">
            <Field
              label="Portfolio tickers"
              wide
            >
              <input
                value={tickers}
                onChange={(event) =>
                  setTickers(
                    event.target.value
                  )
                }
                placeholder="RELIANCE, TCS, INFY"
              />

              <small>
                Separate instruments with
                commas.
              </small>
            </Field>
          </div>

          {/* ==================================================
              PARAMETERS
              ================================================== */}

          <div className="mc-grid">
            <Field label="Initial capital">
              <input
                type="number"
                min="1"
                value={initialAmount}
                onChange={(event) =>
                  setInitialAmount(
                    event.target.value
                  )
                }
              />
            </Field>

            <Field label="Horizon">
              <div className="mc-input-unit">
                <input
                  type="number"
                  min="0.1"
                  max="100"
                  step="0.1"
                  value={years}
                  onChange={(event) =>
                    setYears(
                      event.target.value
                    )
                  }
                />

                <span>YEARS</span>
              </div>
            </Field>

            <Field label="Simulations">
              <input
                type="number"
                min="1"
                max="100000"
                value={simulations}
                onChange={(event) =>
                  setSimulations(
                    event.target.value
                  )
                }
              />
            </Field>

            <Field label="Strategy">
              <select
                value={strategy}
                onChange={(event) =>
                  setStrategy(
                    event.target.value
                  )
                }
              >
                <option value="rebalance">
                  Rebalance
                </option>

                <option value="buy_and_hold">
                  Buy & Hold
                </option>
              </select>
            </Field>

            <Field label="Annual drag">
              <div className="mc-input-unit">
                <input
                  type="number"
                  min="0"
                  max="0.99"
                  step="0.001"
                  value={annualDrag}
                  onChange={(event) =>
                    setAnnualDrag(
                      event.target.value
                    )
                  }
                />

                <span>DECIMAL</span>
              </div>

              <small>
                0.01 = 1% annual drag.
              </small>
            </Field>
          </div>

          {/* ==================================================
              UNLOCK
              ================================================== */}

          {!unlocked ? (
            <div className="mc-unlock">
              <div>
                <div className="mc-pro-label">
                  MONTE CARLO PRO
                </div>

                <h2>
                  Unlock portfolio simulation
                </h2>

                <p>
                  Run the simulation and
                  access the complete risk
                  summary for your portfolio.
                </p>
              </div>

              <button
                type="button"
                className="mc-button primary"
                onClick={handleUnlock}
                disabled={
                  unlocking || loading
                }
              >
                {unlocking
                  ? "Opening payment..."
                  : "Unlock for ₹499"}
              </button>
            </div>
          ) : (
            <div className="mc-run-row">
              <div>
                <div className="mc-pro-label">
                  ENTITLEMENT ACTIVE
                </div>

                <p>
                  Monte Carlo is ready to
                  run.
                </p>
              </div>

              <button
                className="mc-button primary"
                type="submit"
                disabled={loading}
              >
                {loading
                  ? "Running simulation..."
                  : "Run Monte Carlo"}
              </button>
            </div>
          )}
        </form>

        {/* ====================================================
            ERROR
            ==================================================== */}

        {error && (
          <div className="mc-error">
            <strong>
              SIMULATION UNAVAILABLE
            </strong>

            <span>{error}</span>
          </div>
        )}

        {/* ====================================================
            READY
            ==================================================== */}

        {unlocked &&
          !result &&
          !error && (
            <div className="mc-ready">
              <span>READY</span>

              Configure the parameters above
              and run the simulation.
            </div>
          )}

        {/* ====================================================
            RESULTS
            ==================================================== */}

        {result && (
          <MonteCarloResults
            result={result}
          />
        )}
      </div>
    </section>
  );
}

// ============================================================
// FIELD
// ============================================================

function Field({
  label,
  children,
  wide = false,
}) {
  return (
    <div
      className={`mc-field ${
        wide ? "wide" : ""
      }`}
    >
      <label>{label}</label>

      {children}
    </div>
  );
}

// ============================================================
// FORMATTING
// ============================================================

function formatCurrency(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "—";
  }

  return new Intl.NumberFormat(
    "en-IN",
    {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }
  ).format(number);
}

function formatPercent(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "—";
  }

  return `${(
    number * 100
  ).toFixed(2)}%`;
}

// ============================================================
// RESULTS
// ============================================================

function MonteCarloResults({
  result,
}) {
  const cards = [
    [
      "Median final wealth",
      formatCurrency(
        result.median_final_wealth
      ),
    ],

    [
      "Mean final wealth",
      formatCurrency(
        result.mean_final_wealth
      ),
    ],

    [
      "5th percentile",
      formatCurrency(
        result.percentile_5
      ),
    ],

    [
      "95th percentile",
      formatCurrency(
        result.percentile_95
      ),
    ],

    [
      "Probability of loss",
      formatPercent(
        result.probability_of_loss
      ),
    ],

    [
      "CVaR 95% loss",
      formatCurrency(
        result.cvar_95_loss
      ),
    ],

    [
      "Median max drawdown",
      formatPercent(
        result.median_max_drawdown
      ),
    ],

    [
      "95th percentile max drawdown",
      formatPercent(
        result.percentile_95_max_drawdown
      ),
    ],
  ];

  return (
    <div className="mc-results">
      {/* ======================================================
          RESULT HEADER
          ====================================================== */}

      <div className="mc-results-heading">
        <div>
          <div className="mc-eyebrow">
            SIMULATION RESULT
          </div>

          <h2>
            {(result.tickers || []).join(
              " · "
            )}
          </h2>
        </div>

        <div className="mc-count">
          <strong>
            {Number(
              result.simulations || 0
            ).toLocaleString("en-IN")}
          </strong>

          <span>simulations</span>
        </div>
      </div>

      {/* ======================================================
          SUMMARY CARDS
          ====================================================== */}

      <div className="mc-summary">
        {cards.map(
          ([label, value]) => (
            <div
              className="mc-card"
              key={label}
            >
              <span>{label}</span>

              <strong>{value}</strong>
            </div>
          )
        )}
      </div>

      {/* ======================================================
          PARAMETERS
          ====================================================== */}

      <div className="mc-capital-summary">
        <Stat
          label="Initial capital"
          value={formatCurrency(
            result.initial_amount
          )}
        />

        <Stat
          label="Horizon"
          value={`${result.years} years`}
        />

        <Stat
          label="Strategy"
          value={
            result.strategy ===
            "buy_and_hold"
              ? "Buy & Hold"
              : "Rebalance"
          }
        />

        <Stat
          label="Annual drag"
          value={formatPercent(
            result.annual_drag
          )}
        />
      </div>

      {/* ======================================================
          DISTRIBUTION
          ====================================================== */}

      <div className="mc-distribution-placeholder">
        <div className="mc-eyebrow">
          DISTRIBUTION
        </div>

        <h3>
          Terminal wealth distribution
        </h3>

        <p>
          The current API response provides
          percentile and risk statistics,
          but not the individual simulated
          terminal values. The summary above
          is rendered directly from the API
          response.
        </p>
      </div>
    </div>
  );
}

// ============================================================
// STAT
// ============================================================

function Stat({
  label,
  value,
}) {
  return (
    <div>
      <span>{label}</span>

      <strong>{value}</strong>
    </div>
  );
}