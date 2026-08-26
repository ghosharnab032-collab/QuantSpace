import { useEffect, useMemo, useState } from "react";

import {
  getAsset,
  getHistoricalData,
} from "./api/marketdata";

import "./components/MarketData.css";


// ============================================================
// CONSTANTS
// ============================================================

const QUICK_TICKERS = [
  "RELIANCE",
  "TCS",
  "INFY",
  "HDFCBANK",
  "ICICIBANK",
];

const RANGES = [
  ["1M", 1],
  ["3M", 3],
  ["6M", 6],
  ["1Y", 12],
  ["5Y", 60],
];


// ============================================================
// HELPERS
// ============================================================

function formatDate(date) {
  const value = new Date(date);

  if (Number.isNaN(value.getTime())) {
    return "";
  }

  const year = value.getFullYear();
  const month = String(
    value.getMonth() + 1
  ).padStart(2, "0");

  const day = String(
    value.getDate()
  ).padStart(2, "0");

  return `${year}-${month}-${day}`;
}


function getDateRange(months) {
  const end = new Date();
  const start = new Date(end);

  start.setMonth(
    start.getMonth() - months
  );

  return {
    start: formatDate(start),
    end: formatDate(end),
  };
}


function numberValue(value) {
  const number = Number(value);

  return Number.isFinite(number)
    ? number
    : null;
}


function formatPrice(value) {
  const number = numberValue(value);

  if (number === null) {
    return "—";
  }

  return `₹${number.toLocaleString(
    "en-IN",
    {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }
  )}`;
}


function formatVolume(value) {
  const number = numberValue(value);

  if (number === null) {
    return "—";
  }

  return number.toLocaleString("en-IN");
}


function getLatest(data) {
  if (!Array.isArray(data) || !data.length) {
    return null;
  }

  return data[data.length - 1];
}


function getPrevious(data) {
  if (!Array.isArray(data) || data.length < 2) {
    return null;
  }

  return data[data.length - 2];
}


// ============================================================
// COMPONENT
// ============================================================

export default function Assets() {
  const [input, setInput] =
    useState("RELIANCE");

  const [ticker, setTicker] =
    useState("RELIANCE");

  const [range, setRange] =
    useState("1Y");

  const [history, setHistory] =
    useState([]);

  const [metadata, setMetadata] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  const [apiOnline, setApiOnline] =
    useState(true);


  // ==========================================================
  // LOAD ASSET
  // ==========================================================

  async function loadAsset(
    symbol = input,
    selectedRange = range
  ) {
    const clean =
      String(symbol || "")
        .trim()
        .toUpperCase();

    if (!clean) {
      setError(
        "Enter an NSE ticker."
      );
      return;
    }

    setLoading(true);
    setError("");

    try {
      const {
        start,
        end,
      } = getDateRange(
        RANGES.find(
          ([name]) =>
            name === selectedRange
        )?.[1] || 12
      );

      const [
        assetResponse,
        historyResponse,
      ] = await Promise.all([
        getAsset(clean),
        getHistoricalData({
          ticker: clean,
          start,
          end,
        }),
      ]);

      const rows =
        historyResponse?.data || [];

      setTicker(clean);
      setMetadata(assetResponse);
      setHistory(rows);
      setApiOnline(true);
    } catch (err) {
      console.error(
        "[Assets] Load failed:",
        err
      );

      setApiOnline(
        Boolean(
          err?.response?.status !== 404
        )
      );

      setError(
        err?.response?.data?.detail ||
        "Market-data API returned an error."
      );

      setMetadata(null);
      setHistory([]);
    } finally {
      setLoading(false);
    }
  }


  // ==========================================================
  // INITIAL LOAD
  // ==========================================================

  useEffect(() => {
    loadAsset(
      "RELIANCE",
      "1Y"
    );

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // ==========================================================
  // RANGE CHANGE
  // ==========================================================

  async function changeRange(
    nextRange
  ) {
    setRange(nextRange);

    await loadAsset(
      ticker,
      nextRange
    );
  }


  // ==========================================================
  // QUICK ACCESS
  // ==========================================================

  function selectTicker(symbol) {
    setInput(symbol);
    loadAsset(
      symbol,
      range
    );
  }


  // ==========================================================
  // DERIVED DATA
  // ==========================================================

  const latest =
    useMemo(
      () => getLatest(history),
      [history]
    );

  const previous =
    useMemo(
      () => getPrevious(history),
      [history]
    );


  const change = useMemo(() => {
    const current =
      numberValue(latest?.close);

    const previousClose =
      numberValue(previous?.close);

    if (
      current === null ||
      previousClose === null ||
      previousClose === 0
    ) {
      return null;
    }

    const absolute =
      current - previousClose;

    const percentage =
      (absolute / previousClose) *
      100;

    return {
      absolute,
      percentage,
    };
  }, [latest, previous]);


  // ==========================================================
  // RENDER
  // ==========================================================

  return (
    <main className="market-data-page">

      {/* ======================================================
          HEADER
      ====================================================== */}

      <header className="market-data-header">

        <div className="market-data-eyebrow">
          QUANT PLATFORM / ASSETS / NSE
        </div>

        <div className="market-data-title-row">

          <div>
            <h1 className="market-data-title">
              Assets
            </h1>

            <p className="market-data-description">
              Explore NSE securities,
              historical prices and
              quantitative market data.
            </p>
          </div>

          <div className="market-data-status-pill">
            <span />
            {apiOnline
              ? "LIVE DATA"
              : "API OFFLINE"}
          </div>

        </div>
      </header>


      {/* ======================================================
          CONTENT
      ====================================================== */}

      <section className="market-data-content">

        {/* ====================================================
            SEARCH
        ==================================================== */}

        <div className="market-data-query">

          <div className="market-data-query-label">
            ASSET SEARCH
          </div>

          <div className="market-data-query-grid">

            <div
              className="market-data-field market-data-ticker-field"
            >
              <label>
                NSE TICKER
              </label>

              <div className="market-data-input-shell">

                <span>
                  NSE
                </span>

                <input
                  value={input}
                  onChange={(event) =>
                    setInput(
                      event.target.value
                    )
                  }
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter"
                    ) {
                      loadAsset();
                    }
                  }}
                  placeholder="RELIANCE"
                  spellCheck={false}
                />

              </div>
            </div>

            <button
              className="market-data-load-button"
              onClick={() =>
                loadAsset()
              }
              disabled={loading}
            >
              {loading
                ? "Loading..."
                : "Search"}
            </button>

          </div>


          {/* QUICK ACCESS */}

          <div className="market-data-quick-row">

            <span>
              QUICK ACCESS
            </span>

            <div className="market-data-quick-buttons">

              {QUICK_TICKERS.map(
                (symbol) => (
                  <button
                    key={symbol}
                    className={
                      "market-data-quick-button" +
                      (
                        ticker === symbol
                          ? " active"
                          : ""
                      )
                    }
                    onClick={() =>
                      selectTicker(
                        symbol
                      )
                    }
                    disabled={loading}
                  >
                    {symbol}
                  </button>
                )
              )}

            </div>

          </div>


          {/* RANGE */}

          <div className="market-data-quick-row">

            <span>
              HISTORY
            </span>

            <div className="market-data-quick-buttons">

              {RANGES.map(
                ([name]) => (
                  <button
                    key={name}
                    className={
                      "market-data-quick-button" +
                      (
                        range === name
                          ? " active"
                          : ""
                      )
                    }
                    onClick={() =>
                      changeRange(
                        name
                      )
                    }
                    disabled={loading}
                  >
                    {name}
                  </button>
                )
              )}

            </div>

          </div>

        </div>


        {/* ====================================================
            ERROR
        ==================================================== */}

        {error && (
          <div className="market-data-error">

            <strong>
              Data issue
            </strong>

            <span>
              {error}
            </span>

          </div>
        )}


        {/* ====================================================
            ASSET METADATA
        ==================================================== */}

        {metadata && (
          <section className="market-data-asset-card">

            <div className="market-data-asset-main">

              <div className="market-data-card-eyebrow">
                ASSET
              </div>

              <h2>
                {metadata.ticker ||
                  ticker}
              </h2>

              <p>
                {metadata.name ||
                  "NSE Equity"}
              </p>

            </div>


            <div className="market-data-stat">
              <span>
                Exchange
              </span>

              <strong>
                {metadata.exchange ||
                  "NSE"}
              </strong>
            </div>


            <div className="market-data-stat">
              <span>
                Instrument
              </span>

              <strong>
                {metadata.instrument_type ||
                  "EQ"}
              </strong>
            </div>


            <div className="market-data-stat">
              <span>
                ISIN
              </span>

              <strong>
                {metadata.isin ||
                  "—"}
              </strong>
            </div>

          </section>
        )}


        {/* ====================================================
            PRICE HISTORY SUMMARY
        ==================================================== */}

        {history.length > 0 && (
          <section className="market-data-results">

            <div className="market-data-results-header">

              <div>

                <div className="market-data-card-eyebrow">
                  PRICE HISTORY
                </div>

                <h2>
                  {ticker}
                </h2>

                <p>
                  {history[0]?.date}
                  {" — "}
                  {history[
                    history.length - 1
                  ]?.date}
                </p>

              </div>

              <div className="market-data-session-count">

                <strong>
                  {history.length}
                </strong>

                <span>
                  Sessions
                </span>

              </div>

            </div>


            {/* ==================================================
                METRICS
            ================================================== */}

            {latest && (
              <div className="market-data-metrics">

                <div className="market-data-metric">

                  <span>
                    Latest Close
                  </span>

                  <strong>
                    {formatPrice(
                      latest.close
                    )}
                  </strong>

                  {change && (
                    <small
                      className={
                        change.percentage >= 0
                          ? "market-data-positive"
                          : "market-data-negative"
                      }
                    >
                      {change.absolute >= 0
                        ? "+"
                        : ""}
                      {change.absolute.toFixed(
                        2
                      )}
                      {" "}
                      (
                      {change.percentage >= 0
                        ? "+"
                        : ""}
                      {change.percentage.toFixed(
                        2
                      )}
                      %)
                    </small>
                  )}

                </div>


                <div className="market-data-metric">

                  <span>
                    Open
                  </span>

                  <strong>
                    {formatPrice(
                      latest.open
                    )}
                  </strong>

                </div>


                <div className="market-data-metric">

                  <span>
                    High
                  </span>

                  <strong>
                    {formatPrice(
                      latest.high
                    )}
                  </strong>

                </div>


                <div className="market-data-metric">

                  <span>
                    Low
                  </span>

                  <strong>
                    {formatPrice(
                      latest.low
                    )}
                  </strong>

                </div>


                <div className="market-data-metric">

                  <span>
                    Volume
                  </span>

                  <strong>
                    {formatVolume(
                      latest.volume
                    )}
                  </strong>

                </div>

              </div>
            )}


            {/* ==================================================
                TABLE
            ================================================== */}

            <section className="market-data-panel">

              <div className="market-data-panel-header">

                <div>
                  <div className="market-data-card-eyebrow">
                    HISTORICAL DATA
                  </div>

                  <h3>
                    Daily OHLCV
                  </h3>
                </div>

                <span>
                  {history.length} rows
                </span>

              </div>


              <div className="market-data-table-wrapper">

                <table className="market-data-table">

                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Open</th>
                      <th>High</th>
                      <th>Low</th>
                      <th>Close</th>
                      <th>Volume</th>
                    </tr>
                  </thead>

                  <tbody>

                    {[
                      ...history,
                    ]
                      .reverse()
                      .slice(0, 100)
                      .map(
                        (row, index) => (
                          <tr
                            key={
                              `${row.date}-${index}`
                            }
                          >
                            <td>
                              {row.date}
                            </td>

                            <td>
                              {formatPrice(
                                row.open
                              )}
                            </td>

                            <td>
                              {formatPrice(
                                row.high
                              )}
                            </td>

                            <td>
                              {formatPrice(
                                row.low
                              )}
                            </td>

                            <td>
                              {formatPrice(
                                row.close
                              )}
                            </td>

                            <td>
                              {formatVolume(
                                row.volume
                              )}
                            </td>
                          </tr>
                        )
                      )}

                  </tbody>

                </table>

              </div>

            </section>

          </section>
        )}


        {/* ====================================================
            EMPTY
        ==================================================== */}

        {!loading &&
          !error &&
          history.length === 0 && (
            <div className="market-data-empty">

              <div className="market-data-card-eyebrow">
                NO DATA
              </div>

              <h3>
                No historical prices
              </h3>

              <p>
                Search for an NSE ticker
                to load its market history.
              </p>

            </div>
          )}

      </section>

    </main>
  );
}