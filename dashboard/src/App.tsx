import { useState } from "react";
import { AccuracyDashboard } from "./pages/AccuracyDashboard";
import { CalibrationExplorer } from "./pages/CalibrationExplorer";
import { DomainEffects } from "./pages/DomainEffects";
import { PracticalUse } from "./pages/PracticalUse";
import { Report } from "./pages/Report";
import "./App.css";

type Page = "report" | "overview" | "calibration" | "domain" | "practical";

function App() {
  const [page, setPage] = useState<Page>("report");

  return (
    <div className="app">
      <header className="header">
        <h1>Kalshi Market Research</h1>
        <p className="subtitle">
          Do prices mean the same thing across categories and time horizons?
        </p>
        <nav className="nav">
          {(
            [
              ["report", "Report"],
              ["overview", "Overview"],
              ["calibration", "Calibration Explorer"],
              ["domain", "Domain Effects"],
              ["practical", "Practical Use"],
            ] as [Page, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              className={`nav-btn ${page === key ? "active" : ""}`}
              onClick={() => setPage(key)}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>
      <main className="main">
        {page === "report" && <Report />}
        {page === "overview" && <AccuracyDashboard />}
        {page === "calibration" && <CalibrationExplorer />}
        {page === "domain" && <DomainEffects />}
        {page === "practical" && <PracticalUse />}
      </main>
    </div>
  );
}

export default App;
