import client from "./client";

export async function runMonteCarlo(payload) {
  const response = await client.post(
    "/quant/monte-carlo",
    payload
  );

  return response.data;
}