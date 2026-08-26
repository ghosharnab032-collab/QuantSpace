import { useMemo, useState } from "react";
import {
  getHistoricalData,
  getAsset,
} from "../api/marketdata";
import MarketChart from "./MarketChart";
import "./MarketData.css";

const QUICK_TICKERS = [
  "RELIANCE",
  "TCS",
  "INFY",
  "HDFCBANK",
  "ICICIBANK",
];

export default function MarketData() {
  const [ticker, setTicker] = useState("RELIANCE");
  const [start, setStart] = useState("2026-01-01");
  const [end, setEnd] = useState("2026-08-19");
  const [data, setData] = useState(null);
  const [asset, setAsset] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadMarketData(symbol = ticker) {
    const normalized = symbol.trim().toUpperCase();

    if (!normalized) {
      setError("Enter a ticker.");
      return;
    }

    if (start && end && start > end) {
      setError("Start date cannot be after end date.");
      return;
    }

    setTicker(normalized);
    setError("");
    setLoading(true);

    try {
      const [history, metadata] = await Promise.all([
        getHistoricalData({
          ticker: normalized,
          start,
          end,
        }),
        getAsset(normalized),
      ]);

      setData(history);
      setAsset(metadata);
    } catch (err) {
      const detail = err?.response?.data?.detail;

      if (Array.isArray(detail)) {
        setError(detail.map((item) => item.msg).join(", "));
      } else {
        setError(
          detail ||
            err?.message ||
            "Unable to load market data."
        );
      }

      setData(null);
      setAsset(null);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    loadMarketData();
  }

  function handleQuickTicker(symbol) {
    loadMarketData(symbol);
  }

  return (
    <section className="market-data-page">
      <header className="market-data-header">
        <div className="market-data-eyebrow">
          QUANT PLATFORM / MARKET DATA / NSE
        </div>

        <div className="market-data-title-row">
          <div>
            <h1 className="market-data-title">
              Market Data
            </h1>

            <p className="market-data-description">
              Query, inspect and analyze historical market prices
              from the unified quantitative data layer.
            </p>
          </div>

          <div className="market-data-status-pill">
            <span />
            API ONLINE
          </div>
        </div>
      </header>

      <div className="market-data-content">
        <form
          className="market-data-query"
          onSubmit={handleSubmit}
        >
          <div className="market-data-query-label">
            HISTORICAL DATA QUERY
          </div>

          <div className="market-data-query-grid">
            <div className="market-data-field market-data-ticker-field">
              <label htmlFor="marketTicker">NSE ticker</label>

              <div className="market-data-input-shell">
                <span>NSE</span>

                <input
                  id="marketTicker"
                  value={ticker}
                  onChange={(event) =>
                    setTicker(event.target.value.toUpperCase())
                  }
                  placeholder="RELIANCE"
                  autoCapitalize="characters"
                  autoComplete="off"
                  spellCheck={false}
                />
              </div>
            </div>

            <div className="market-data-field">
              <label htmlFor="marketStart">Start date</label>
              <input
                id="marketStart"
                type="date"
                value={start}
                onChange={(event) => setStart(event.target.value)}
              />
            </div>

            <div className="market-data-field">
              <label htmlFor="marketEnd">End date</label>
              <input
                id="marketEnd"
                type="date"
                value={end}
                onChange={(event) => setEnd(event.target.value)}
              />
            </div>

            <button
              className="market-data-load-button"
              type="submit"
              disabled={loading}
            >
              {loading ? "Loading..." : "Load data"}
            </button>
          </div>

          <div className="market-data-quick-row">
            <span>QUICK ACCESS</span>

            <div className="market-data-quick-buttons">
              {QUICK_TICKERS.map((symbol) => (
                <button
                  key={symbol}
                  type="button"
                  className={
                    ticker === symbol
                      ? "market-data-quick-button active"
                      : "market-data-quick-button"
                  }
                  onClick={() => handleQuickTicker(symbol)}
                  disabled={loading}
                >
                  {symbol}
                </button>
              ))}
            </div>
          </div>
        </form>

        {error && (
          <div className="market-data-error">
            <strong>Market data unavailable</strong>
            <span>{error}</span>
          </div>
        )}

        {asset && <AssetSummary asset={asset} />}

        {data && <HistoricalResults data={data} />}
      </div>
    </section>
  );
}

function AssetSummary({ asset }) {
  return (
    <section className="market-data-asset-card">
      <div className="market-data-asset-main">
        <div className="market-data-card-eyebrow">
          ASSET
        </div>

        <h2>{asset.ticker || "—"}</h2>

        <p>{asset.name || "NSE equity"}</p>
      </div>

      <Stat
        label="Exchange"
        value={asset.exchange || "NSE"}
      />

      <Stat
        label="Instrument"
        value={asset.instrument_type || "Equity"}
      />

      <Stat
        label="Source"
        value="Unified data layer"
      />
    </section>
  );
}

function Stat({ label, value }) {
  return (
    <div className="market-data-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function HistoricalResults({ data }) {
  const rows = useMemo(() => {
    const sourceRows = Array.isArray(data?.data)
      ? data.data
      : [];

    return [...sourceRows].sort((a, b) =>
      String(a.date ?? a.trade_date ?? "").localeCompare(
        String(b.date ?? b.trade_date ?? "")
      )
    );
  }, [data]);

  if (!rows.length) {
    return (
      <div className="market-data-empty">
        <div className="market-data-card-eyebrow">
          NO OBSERVATIONS
        </div>
        <h3>No historical data</h3>
        <p>
          The API returned no observations for this ticker and
          date range.
        </p>
      </div>
    );
  }

  const latest = rows[rows.length - 1];
  const previous = rows.length > 1 ? rows[rows.length - 2] : null;

  const latestClose = Number(latest?.close);
  const previousClose = Number(previous?.close);

  const dailyChange =
    Number.isFinite(latestClose) &&
    Number.isFinite(previousClose)
      ? latestClose - previousClose
      : null;

  const dailyChangePct =
    dailyChange !== null && previousClose !== 0
      ? (dailyChange / previousClose) * 100
      : null;

  const displayStart =
    data.start ??
    rows[0]?.date ??
    rows[0]?.trade_date;

  const displayEnd =
    data.end ??
    latest?.date ??
    latest?.trade_date;

  const count = Number(data.count ?? rows.length);

  return (
    <div className="market-data-results">
      <div className="market-data-results-header">
        <div>
          <div className="market-data-card-eyebrow">
            PRICE HISTORY
          </div>
          <h2>{data.ticker}</h2>
          <p>
            {displayStart} — {displayEnd}
          </p>
        </div>

        <div className="market-data-session-count">
          <strong>{count.toLocaleString("en-IN")}</strong>
          <span>sessions</span>
        </div>
      </div>

      <div className="market-data-metrics">
        <Metric label="Latest close">
          {formatPrice(latestClose)}
          {dailyChangePct !== null && (
            <small
              className={
                dailyChange >= 0
                  ? "market-data-positive"
                  : "market-data-negative"
              }
            >
              {dailyChange >= 0 ? "+" : ""}
              {dailyChange.toFixed(2)} (
              {dailyChangePct >= 0 ? "+" : ""}
              {dailyChangePct.toFixed(2)}%)
            </small>
          )}
        </Metric>

        <Metric
          label="Open"
          value={formatPrice(latest?.open)}
        />

        <Metric
          label="High"
          value={formatPrice(latest?.high)}
        />

        <Metric
          label="Low"
          value={formatPrice(latest?.low)}
        />

        <Metric
          label="Volume"
          value={
            latest?.volume == null
              ? "—"
              : Number(latest.volume).toLocaleString("en-IN")
          }
        />
      </div>

      <section className="market-data-panel">
        <div className="market-data-panel-header">
          <div>
            <div className="market-data-card-eyebrow">
              PRICE CHART
            </div>
            <h3>{data.ticker} historical close</h3>
          </div>

          <span>{rows.length} observations</span>
        </div>

        <div className="market-data-chart">
          <MarketChart data={rows} height={520} />
        </div>
      </section>

      <RecentDataTable data={rows} />
    </div>
  );
}

function Metric({ label, value, children }) {
  return (
    <div className="market-data-metric">
      <span>{label}</span>
      <strong>{value ?? children ?? "—"}</strong>
    </div>
  );
}

function RecentDataTable({ data }) {
  const rows = [...data]
    .sort((a, b) =>
      String(b.date ?? b.trade_date ?? "").localeCompare(
        String(a.date ?? a.trade_date ?? "")
      )
    )
    .slice(0, 20);

  return (
    <section className="market-data-panel">
      <div className="market-data-panel-header">
        <div>
          <div className="market-data-card-eyebrow">
            OHLCV
          </div>
          <h3>Latest trading sessions</h3>
        </div>

        <span>Showing {rows.length} of {data.length}</span>
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
              <th>Source</th>
            </tr>
          </thead>

          <tbody>
            {rows.map((row) => {
              const date = row.date ?? row.trade_date;

              const key = `${row.ticker ?? ""}-${date ?? ""}-${
                row.source ?? ""
              }`;

              return (
                <tr key={key}>
                  <td>{date || "—"}</td>
                  <td>{formatPrice(row.open)}</td>
                  <td>{formatPrice(row.high)}</td>
                  <td>{formatPrice(row.low)}</td>
                  <td>{formatPrice(row.close)}</td>
                  <td>
                    {row.volume == null
                      ? "—"
                      : Number(row.volume).toLocaleString("en-IN")}
                  </td>
                  <td>{row.source || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatPrice(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "—";
  }

  return `₹${number.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}