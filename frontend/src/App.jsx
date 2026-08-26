import { useState } from "react";

import Assets from "./Assets";
import Backtesting from "./components/Backtesting";
import BlackScholes from "./components/BlackScholes";
import MarketData from "./components/MarketData";
import MonteCarlo from "./components/MonteCarlo";
import PortfolioOptimizer from "./components/PortfolioOptimizer";
import Dashboard from "./components/Dashboard";

import Login from "./auth/Login";
import { useAuth } from "./auth/AuthContext";

import "./App.css";


/* =========================================================
   TOOLS
   ========================================================= */

const TOOLS = [
  {
    id: "dashboard",
    label: "Dashboard",
    description: "Quant research hub",
    component: Dashboard,
    icon: "▦",
  },
  {
    id: "assets",
    label: "Assets",
    description: "NSE market data",
    component: Assets,
    icon: "▥",
  },
  {
    id: "market-data",
    label: "Market Data",
    description: "Prices and history",
    component: MarketData,
    icon: "⌁",
  },
  {
    id: "backtesting",
    label: "Backtesting",
    description: "Strategy research",
    component: Backtesting,
    icon: "↗",
  },
  {
    id: "optimizer",
    label: "Portfolio Optimizer",
    description: "Portfolio construction",
    component: PortfolioOptimizer,
    icon: "◔",
  },
  {
    id: "monte-carlo",
    label: "Monte Carlo",
    description: "Risk simulation",
    component: MonteCarlo,
    icon: "〰",
  },
  {
    id: "black-scholes",
    label: "Black-Scholes",
    description: "Options analytics",
    component: BlackScholes,
    icon: "Σ",
  },
];


/* =========================================================
   APP
   ========================================================= */

export default function App() {
  const {
    isAuthenticated,
    loading,
    logout,
  } = useAuth();

  const [activeTool, setActiveTool] =
    useState("dashboard");

  const [sidebarOpen, setSidebarOpen] =
    useState(false);


  /* =======================================================
     AUTH LOADING
     ======================================================= */

  if (loading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-mark">
          QS
        </div>

        <span>
          LOADING QUANT SPACE
        </span>
      </div>
    );
  }


  /* =======================================================
     AUTHENTICATION
     ======================================================= */

  if (!isAuthenticated) {
    return <Login />;
  }


  /* =======================================================
     ACTIVE TOOL
     ======================================================= */

  const active =
    TOOLS.find(
      (tool) => tool.id === activeTool
    ) || TOOLS[0];

  const ActiveComponent =
    active.component;


  /* =======================================================
     NAVIGATION
     ======================================================= */

  function selectTool(id) {
    setActiveTool(id);
    setSidebarOpen(false);
  }


  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <div className="app-shell">

      {/* ===================================================
          SIDEBAR
          =================================================== */}

      <aside
        className={`app-sidebar ${
          sidebarOpen
            ? "app-sidebar-open"
            : ""
        }`}
      >

        {/* BRAND */}

        <div className="app-brand">

          <div className="app-brand-mark">
            QS
          </div>

          <div className="app-brand-name">
            Quant Space
          </div>

        </div>


        {/* TOOLS */}

        <div className="app-tools">

          <div className="app-nav-label">
            TOOLS
          </div>

          <nav className="app-nav">

            {TOOLS.map((tool) => (

              <button
                key={tool.id}
                type="button"
                className={
                  activeTool === tool.id
                    ? "app-nav-item active"
                    : "app-nav-item"
                }
                onClick={() =>
                  selectTool(tool.id)
                }
              >

                <span className="app-nav-icon">
                  {tool.icon}
                </span>

                <span className="app-nav-copy">

                  <strong>
                    {tool.label}
                  </strong>

                  <small>
                    {tool.description}
                  </small>

                </span>

              </button>

            ))}

          </nav>

        </div>


        {/* SIDEBAR FOOTER */}

        <div className="app-sidebar-footer">

          <div className="app-sidebar-api-status">

            <span className="app-status-dot" />

            API ONLINE

          </div>

          <small>
            127.0.0.1:8000
          </small>

        </div>

      </aside>


      {/* ===================================================
          MAIN
          =================================================== */}

      <div className="app-main">

        {/* TOPBAR */}

        <header className="app-topbar">

          <button
            type="button"
            className="app-mobile-menu"
            onClick={() =>
              setSidebarOpen(
                (value) => !value
              )
            }
            aria-label="Toggle navigation"
          >
            ☰
          </button>


          {/* BREADCRUMB */}

          <div className="app-breadcrumb">

            <span>
              QUANT SPACE
            </span>

            <b>/</b>

            <strong>
              {active.label.toUpperCase()}
            </strong>

          </div>


          {/* TOPBAR ACTIONS */}

          <div className="app-topbar-actions">

            <div className="app-status">

              <span className="app-status-dot" />

              API ONLINE

            </div>

            <button
              type="button"
              className="app-logout"
              onClick={logout}
            >
              LOGOUT
            </button>

          </div>

        </header>


        {/* CONTENT */}

        <main className="app-content">

          <ActiveComponent />

        </main>

      </div>


      {/* ===================================================
          MOBILE BACKDROP
          =================================================== */}

      {sidebarOpen && (

        <button
          type="button"
          className="app-backdrop"
          aria-label="Close navigation"
          onClick={() =>
            setSidebarOpen(false)
          }
        />

      )}

    </div>
  );
}