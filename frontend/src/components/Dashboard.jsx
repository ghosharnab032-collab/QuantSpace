import "./Dashboard.css";

const MODULES = [
  {
    id: "assets",
    title: "Assets",
    description: "Browse NSE listed companies and market overview.",
    number: "01",
    icon: "▥",
    tone: "blue",
  },
  {
    id: "market-data",
    title: "Market Data",
    description: "Historical prices, charts, and technical data.",
    number: "02",
    icon: "⌁",
    tone: "green",
  },
  {
    id: "backtesting",
    title: "Backtesting",
    description: "Test trading strategies with historical data.",
    number: "03",
    icon: "↗",
    tone: "purple",
  },
  {
    id: "optimizer",
    title: "Portfolio Optimizer",
    description: "Optimize asset allocation and construct portfolios.",
    number: "04",
    icon: "◔",
    tone: "orange",
  },
  {
    id: "monte-carlo",
    title: "Monte Carlo",
    description: "Run simulations and analyze potential outcomes.",
    number: "05",
    icon: "∿",
    tone: "cyan",
  },
  {
    id: "black-scholes",
    title: "Black-Scholes",
    description: "Options pricing and Greeks calculation.",
    number: "06",
    icon: "Σ",
    tone: "yellow",
  },
];

export default function Dashboard({ onNavigate }) {
  return (
    <section className="dashboard">
      <div className="dashboard-header">
        <div>
          <span className="dashboard-kicker">DASHBOARD</span>
          <h1>Welcome to Quant Space</h1>
          <p>Your all-in-one platform for quantitative research and analysis.</p>
        </div>

        <div className="dashboard-live">
          <span />
          API ONLINE
        </div>
      </div>

      <div className="dashboard-grid">
        {MODULES.map((module) => (
          <button
            key={module.id}
            type="button"
            className={`dashboard-card ${module.tone}`}
            onClick={() => onNavigate(module.id)}
          >
            <div className="dashboard-card-top">
              <span className="dashboard-icon">{module.icon}</span>
              <span className="dashboard-number">{module.number}</span>
            </div>

            <div className="dashboard-card-body">
              <h2>{module.title}</h2>
              <p>{module.description}</p>
            </div>

            <span className="dashboard-arrow">→</span>
          </button>
        ))}
      </div>

      <section className="dashboard-activity">
        <div className="dashboard-activity-head">
          <h2>Recent Activity</h2>
          <span>LOCAL SESSION</span>
        </div>

        <div className="dashboard-table">
          <div className="dashboard-row dashboard-row-head">
            <span>TOOL</span>
            <span>DETAILS</span>
            <span>STATUS</span>
          </div>

          <div className="dashboard-row">
            <span className="dashboard-tool">
              <i className="purple">↗</i>
              Backtesting
            </span>
            <span>Moving-average strategy research</span>
            <span className="dashboard-status">READY</span>
          </div>

          <div className="dashboard-row">
            <span className="dashboard-tool">
              <i className="orange">◔</i>
              Portfolio Optimizer
            </span>
            <span>Maximum-Sharpe portfolio construction</span>
            <span className="dashboard-status">READY</span>
          </div>

          <div className="dashboard-row">
            <span className="dashboard-tool">
              <i className="cyan">∿</i>
              Monte Carlo
            </span>
            <span>Simulation and distribution analysis</span>
            <span className="dashboard-status">READY</span>
          </div>
        </div>
      </section>
    </section>
  );
}