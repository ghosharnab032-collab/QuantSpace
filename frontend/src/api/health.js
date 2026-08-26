import api from "./client";

export async function checkHealth() {
  const response = await api.get("/health");
  return response.data;
}