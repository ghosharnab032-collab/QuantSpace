import client from "./client";

// ============================================================
// MONTE CARLO
// ============================================================

export async function runMonteCarlo(payload) {
  const response = await client.post(
    "/quant/monte-carlo",
    payload
  );

  return response.data;
}


// ============================================================
// PORTFOLIO OPTIMIZER
// ============================================================

export async function optimizePortfolio(payload) {
  const response = await client.post(
    "/quant/optimizer",
    payload
  );

  return response.data;
}


// ============================================================
// BLACK-SCHOLES
// ============================================================

export async function runBlackScholes(payload) {
  const response = await client.post(
    "/black-scholes",
    payload
  );

  return response.data;
}


// ============================================================
// BACKTESTING
// ============================================================

export async function runBacktest({
  ticker,
  start,
  end,
  fastMa,
  slowMa,
  initialCapital,
  riskFreeRate,
}) {
  const response = await client.post(
    "/backtesting",
    {
      ticker: ticker.trim().toUpperCase(),

      start: start || null,

      end: end || null,

      fast_ma: Number(fastMa),

      slow_ma: Number(slowMa),

      initial_capital: Number(
        initialCapital
      ),

      risk_free_rate: Number(
        riskFreeRate
      ),
    }
  );

  return response.data;
}