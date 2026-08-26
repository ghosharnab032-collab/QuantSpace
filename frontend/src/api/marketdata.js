import client from "./client";

// ============================================================
// HISTORICAL MARKET DATA
// ============================================================

export async function getHistoricalData({
  ticker,
  start,
  end,
}) {
  const symbol = ticker.trim().toUpperCase();

  if (!symbol) {
    throw new Error("Ticker is required.");
  }

  const params = {};

  if (start) {
    params.start = start;
  }

  if (end) {
    params.end = end;
  }

  console.log(
    "[MARKET DATA] Request:",
    symbol,
    params
  );

  const response = await client.get(
    `/market-data/${encodeURIComponent(symbol)}/history`,
    { params }
  );

  console.log(
    "[MARKET DATA] Response:",
    response.data
  );

  return response.data;
}


// ============================================================
// ASSET METADATA
// ============================================================

export async function getAsset(ticker) {
  const symbol = ticker.trim().toUpperCase();

  if (!symbol) {
    throw new Error("Ticker is required.");
  }

  const response = await client.get(
    `/market-data/assets/${encodeURIComponent(symbol)}`
  );

  return response.data;
}