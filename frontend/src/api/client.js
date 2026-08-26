import axios from "axios";

const client = axios.create({
baseURL: `${import.meta.env.VITE_API_URL || ""}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");

  console.log(
    "[API REQUEST]",
    config.method?.toUpperCase(),
    config.url,
    "HAS TOKEN:",
    Boolean(token)
  );

  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

export default client;