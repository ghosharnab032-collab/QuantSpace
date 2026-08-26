import { useState } from "react";

import { useAuth } from "./AuthContext";

import "./Login.css";

export default function Login() {
  const { login, register } = useAuth();

  const [mode, setMode] = useState("login");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();

    setError("");

    if (!email.trim()) {
      setError("Email is required.");
      return;
    }

    if (!password) {
      setError("Password is required.");
      return;
    }

    setLoading(true);

    try {
      if (mode === "login") {
        await login(
          email.trim(),
          password
        );
      } else {
        await register(
          email.trim(),
          password
        );

        // Registration does not necessarily return
        // an access token, so log in afterwards.
        await login(
          email.trim(),
          password
        );
      }
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        "Authentication failed.";

      setError(detail);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">

        <div className="login-logo">
          QS
        </div>

        <div className="login-kicker">
          QUANT SPACE
        </div>

        <h1>
          {mode === "login"
            ? "Welcome back"
            : "Create account"}
        </h1>

        <p className="login-subtitle">
          {mode === "login"
            ? "Sign in to continue to Quant Space."
            : "Create your Quant Space account."}
        </p>

        <form onSubmit={handleSubmit}>

          <label>
            EMAIL
          </label>

          <input
            type="email"
            value={email}
            onChange={(event) =>
              setEmail(event.target.value)
            }
            placeholder="you@example.com"
            autoComplete="email"
          />

          <label>
            PASSWORD
          </label>

          <input
            type="password"
            value={password}
            onChange={(event) =>
              setPassword(event.target.value)
            }
            placeholder="Password"
            autoComplete={
              mode === "login"
                ? "current-password"
                : "new-password"
            }
          />

          {error && (
            <div className="login-error">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
          >
            {loading
              ? "Please wait..."
              : mode === "login"
                ? "Sign in"
                : "Create account"}
          </button>

        </form>

        <button
          type="button"
          className="login-switch"
          onClick={() => {
            setMode(
              mode === "login"
                ? "register"
                : "login"
            );

            setError("");
          }}
        >
          {mode === "login"
            ? "Create an account"
            : "Already have an account? Sign in"}
        </button>

      </div>
    </div>
  );
}