import { useMemo, useState } from "react";
import "./MarketChart.css";

const RANGES = [
  ["1M", 22],
  ["3M", 66],
  ["6M", 132],
  ["1Y", 264],
  ["5Y", 1320],
  ["ALL", null],
];

function num(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function dateOf(row) {
  return String(row?.date ?? row?.trade_date ?? "");
}

function money(value) {
  const n = num(value);
  return n === null
    ? "—"
    : `₹${n.toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
}

function shortVolume(value) {
  const n = num(value);
  if (n === null) return "—";
  if (Math.abs(n) >= 1e7) return `${(n / 1e7).toFixed(2)} Cr`;
  if (Math.abs(n) >= 1e5) return `${(n / 1e5).toFixed(2)} L`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)} K`;
  return n.toLocaleString("en-IN");
}

function prettyDate(value) {
  if (!value) return "—";
  const d = new Date(`${value}T00:00:00`);
  return Number.isNaN(d.getTime())
    ? value
    : d.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
}

export default function MarketChart({ data = [], height = 560 }) {
  const [range, setRange] = useState("1Y");
  const [mode, setMode] = useState("candles");
  const [hoverIndex, setHoverIndex] = useState(null);

  const rows = useMemo(() => {
    if (!Array.isArray(data)) return [];

    return data
      .map((row) => ({
        ...row,
        date: dateOf(row),
        open: num(row?.open),
        high: num(row?.high),
        low: num(row?.low),
        close: num(row?.close),
        volume: num(row?.volume),
      }))
      .filter(
        (r) =>
          r.date &&
          r.open !== null &&
          r.high !== null &&
          r.low !== null &&
          r.close !== null
      )
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [data]);

  const visibleRows = useMemo(() => {
    const selected = RANGES.find(([label]) => label === range);
    const count = selected?.[1];
    if (!count || rows.length <= count) return rows;
    return rows.slice(-count);
  }, [rows, range]);

  if (!visibleRows.length) {
    return (
      <div className="market-chart-empty">
        No valid OHLCV observations available for this range.
      </div>
    );
  }

  const chartWidth = 1200;
  const chartHeight = Math.max(420, Number(height) || 560);
  const left = 76;
  const right = 28;
  const top = 24;
  const priceBottom = mode === "candles" ? chartHeight - 150 : chartHeight - 62;
  const plotWidth = chartWidth - left - right;
  const priceHeight = priceBottom - top;

  const lows = visibleRows.map((r) => r.low);
  const highs = visibleRows.map((r) => r.high);
  const minPrice = Math.min(...lows);
  const maxPrice = Math.max(...highs);
  const priceRange = maxPrice - minPrice || Math.max(maxPrice * 0.02, 1);
  const pad = priceRange * 0.08;
  const min = minPrice - pad;
  const max = maxPrice + pad;

  const volumes = visibleRows.map((r) => r.volume ?? 0);
  const maxVolume = Math.max(...volumes, 1);

  const xFor = (i) =>
    left + (i / Math.max(visibleRows.length - 1, 1)) * plotWidth;

  const yFor = (v) =>
    top + ((max - v) / (max - min)) * priceHeight;

  const closePoints = visibleRows
    .map((r, i) => `${xFor(i)},${yFor(r.close)}`)
    .join(" ");

  const candleWidth = Math.max(
    3,
    Math.min(14, (plotWidth / visibleRows.length) * 0.62)
  );

  const tickValues = Array.from({ length: 5 }, (_, i) =>
    max - ((max - min) * i) / 4
  );

  const xTickCount = Math.min(6, visibleRows.length);
  const xTicks = Array.from({ length: xTickCount }, (_, i) => {
    const index =
      xTickCount === 1
        ? 0
        : Math.round((i / (xTickCount - 1)) * (visibleRows.length - 1));
    return { index, row: visibleRows[index] };
  });

  const hovered =
    hoverIndex === null
      ? visibleRows[visibleRows.length - 1]
      : visibleRows[hoverIndex];

  const hoveredX =
    hoverIndex === null ? null : xFor(hoverIndex);
  const hoveredY =
    hoverIndex === null ? null : yFor(hovered.close);

  const firstClose = visibleRows[0].close;
  const lastClose = visibleRows[visibleRows.length - 1].close;
  const periodChange = lastClose - firstClose;
  const periodPct =
    firstClose !== 0 ? (periodChange / firstClose) * 100 : 0;

  return (
    <div className="market-chart">
      <div className="market-chart-toolbar">
        <div className="market-chart-ranges">
          {RANGES.map(([label]) => (
            <button
              key={label}
              type="button"
              className={range === label ? "active" : ""}
              onClick={() => {
                setRange(label);
                setHoverIndex(null);
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="market-chart-modes">
          <button
            type="button"
            className={mode === "candles" ? "active" : ""}
            onClick={() => setMode("candles")}
          >
            Candles
          </button>
          <button
            type="button"
            className={mode === "line" ? "active" : ""}
            onClick={() => setMode("line")}
          >
            Line
          </button>
        </div>
      </div>

      <div className="market-chart-header">
        <div>
          <span>PRICE</span>
          <strong>{money(hovered.close)}</strong>
          <small>{prettyDate(hovered.date)}</small>
        </div>

        <div className="market-chart-period">
          <span>{range} RETURN</span>
          <strong className={periodChange >= 0 ? "up" : "down"}>
            {periodChange >= 0 ? "+" : ""}
            {periodPct.toFixed(2)}%
          </strong>
        </div>

        <div className="market-chart-ohlc">
          <span>O {money(hovered.open)}</span>
          <span>H {money(hovered.high)}</span>
          <span>L {money(hovered.low)}</span>
          <span>C {money(hovered.close)}</span>
          <span>VOL {shortVolume(hovered.volume)}</span>
        </div>
      </div>

      <div className="market-chart-svg-wrap">
        <svg
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          width="100%"
          height={chartHeight}
          onMouseLeave={() => setHoverIndex(null)}
          role="img"
          aria-label="Historical OHLCV chart"
        >
          {tickValues.map((value, i) => {
            const y = yFor(value);
            return (
              <g key={`yt-${i}`}>
                <line
                  x1={left}
                  x2={chartWidth - right}
                  y1={y}
                  y2={y}
                  className="market-chart-grid"
                />
                <text
                  x={left - 12}
                  y={y + 4}
                  textAnchor="end"
                  className="market-chart-axis"
                >
                  {Math.round(value).toLocaleString("en-IN")}
                </text>
              </g>
            );
          })}

          {mode === "candles" &&
            visibleRows.map((row, i) => {
              const x = xFor(i);
              const rising = row.close >= row.open;
              const bodyTop = yFor(Math.max(row.open, row.close));
              const bodyBottom = yFor(Math.min(row.open, row.close));
              const bodyHeight = Math.max(1.5, bodyBottom - bodyTop);

              return (
                <g
                  key={`candle-${row.date}-${i}`}
                  className={rising ? "candle up" : "candle down"}
                >
                  <line
                    x1={x}
                    x2={x}
                    y1={yFor(row.high)}
                    y2={yFor(row.low)}
                    className="candle-wick"
                  />
                  <rect
                    x={x - candleWidth / 2}
                    y={bodyTop}
                    width={candleWidth}
                    height={bodyHeight}
                    className="candle-body"
                  />
                </g>
              );
            })}

          {mode === "line" && (
            <polyline
              points={closePoints}
              className="market-chart-line"
              fill="none"
            />
          )}

          {visibleRows.map((row, i) => {
            const x = xFor(i);
            const slot = plotWidth / Math.max(visibleRows.length, 1);
            const hitWidth = Math.max(slot, 6);

            return (
              <rect
                key={`hit-${row.date}-${i}`}
                x={x - hitWidth / 2}
                y={top}
                width={hitWidth}
                height={priceHeight}
                fill="transparent"
                onMouseEnter={() => setHoverIndex(i)}
              />
            );
          })}

          {hoverIndex !== null && (
            <>
              <line
                x1={hoveredX}
                x2={hoveredX}
                y1={top}
                y2={chartHeight - 42}
                className="market-chart-crosshair"
              />
              <circle
                cx={hoveredX}
                cy={hoveredY}
                r="5"
                className="market-chart-dot"
              />
            </>
          )}

          {mode === "candles" && (
            <>
              <line
                x1={left}
                x2={chartWidth - right}
                y1={chartHeight - 112}
                y2={chartHeight - 112}
                className="market-chart-volume-divider"
              />

              {visibleRows.map((row, i) => {
                const x = xFor(i);
                const volumeHeight =
                  ((row.volume ?? 0) / maxVolume) * 68;

                return (
                  <rect
                    key={`vol-${row.date}-${i}`}
                    x={x - Math.max(candleWidth / 2, 2)}
                    y={chartHeight - 32 - volumeHeight}
                    width={Math.max(candleWidth, 3)}
                    height={volumeHeight}
                    className={
                      row.close >= row.open
                        ? "volume-bar up"
                        : "volume-bar down"
                    }
                  />
                );
              })}

              <text
                x={left}
                y={chartHeight - 118}
                className="market-chart-volume-label"
              >
                VOLUME
              </text>
            </>
          )}

          {xTicks.map(({ index, row }) => {
            const x = xFor(index);

            return (
              <text
                key={`xt-${row.date}-${index}`}
                x={x}
                y={chartHeight - 12}
                textAnchor="middle"
                className="market-chart-axis"
              >
                {prettyDate(row.date)}
              </text>
            );
          })}
        </svg>
      </div>

      <div className="market-chart-footer">
        <span>
          {visibleRows.length.toLocaleString("en-IN")} sessions
        </span>
        <span>
          {prettyDate(visibleRows[0].date)} —{" "}
          {prettyDate(visibleRows[visibleRows.length - 1].date)}
        </span>
      </div>
    </div>
  );
}