import { useState, useMemo } from "react";
import { useDashboardData } from "../hooks/useData";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from "recharts";

const CAT_COLORS: Record<string, string> = {
  Politics: "#2563eb",
  Economics: "#10b981",
  Sports: "#ef4444",
  Entertainment: "#f59e0b",
  "Climate and Weather": "#06b6d4",
  Elections: "#8b5cf6",
  Financials: "#ec4899",
  Crypto: "#f97316",
  Companies: "#84cc16",
  World: "#6366f1",
  Mentions: "#14b8a6",
  "Science and Technology": "#a855f7",
  Social: "#78716c",
};

const TIME_HORIZONS = ["30+ days", "7-30 days", "1-7 days", "< 24 hours"];

export function CalibrationExplorer() {
  const { data: dash, loading: ld } = useDashboardData();

  const [selectedCats, setSelectedCats] = useState<string[]>(["Politics", "Sports", "Economics"]);
  const [selectedHorizon, setSelectedHorizon] = useState<string>("7-30 days");
  const [view, setView] = useState<"by-category" | "by-time" | "by-liquidity">("by-category");

  const availableCategories = useMemo(() => {
    if (!dash) return [];
    return Object.keys(dash.domain_time_matrix).sort();
  }, [dash]);

  if (ld) return <div className="loading">Loading...</div>;
  if (!dash) return <div className="loading">No data available.</div>;

  const toggleCat = (cat: string) => {
    setSelectedCats((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  const lineCount = view === "by-category"
    ? selectedCats.length
    : view === "by-time"
      ? Object.keys(dash.time_horizon_calibration).length
      : Object.keys(dash.liquidity_calibration).length;
  const legendRows = Math.ceil(lineCount / 3);
  const legendHeight = Math.max(36, legendRows * 24);

  return (
    <div>
      {/* Controls */}
      <div className="card">
        <h2>Calibration Curve Explorer</h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
          Select categories and time horizon to compare calibration curves.
          When a market says 70%, does it happen 70% of the time?
        </p>

        <div className="filters">
          <label style={{ fontWeight: 600, fontSize: "0.85rem" }}>View:</label>
          {(["by-category", "by-time", "by-liquidity"] as const).map((v) => (
            <button
              key={v}
              className={`nav-btn ${view === v ? "active" : ""}`}
              onClick={() => setView(v)}
              style={{ padding: "0.3rem 0.75rem", fontSize: "0.8rem" }}
            >
              {v === "by-category" ? "By Category" : v === "by-time" ? "By Time" : "By Liquidity"}
            </button>
          ))}
        </div>

        {view === "by-category" && (
          <>
            <div className="filters" style={{ marginTop: "0.5rem" }}>
              <label style={{ fontWeight: 600, fontSize: "0.85rem" }}>Horizon:</label>
              {TIME_HORIZONS.map((h) => (
                <button
                  key={h}
                  className={`nav-btn ${selectedHorizon === h ? "active" : ""}`}
                  onClick={() => setSelectedHorizon(h)}
                  style={{ padding: "0.3rem 0.75rem", fontSize: "0.8rem" }}
                >
                  {h}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.5rem" }}>
              {availableCategories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => toggleCat(cat)}
                  style={{
                    padding: "0.2rem 0.6rem",
                    fontSize: "0.75rem",
                    border: `2px solid ${CAT_COLORS[cat] || "#666"}`,
                    borderRadius: 4,
                    background: selectedCats.includes(cat)
                      ? CAT_COLORS[cat] || "#666"
                      : "white",
                    color: selectedCats.includes(cat) ? "white" : CAT_COLORS[cat] || "#666",
                    cursor: "pointer",
                    fontWeight: 600,
                  }}
                >
                  {cat}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Chart */}
      <div className="card">
        <div className="chart-container" style={{ height: 500 + legendHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart margin={{ top: 10, right: 20, bottom: 30, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="mean_predicted"
                type="number"
                domain={[0, 1]}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                label={{ value: "Market Implied Probability", position: "bottom", offset: 10 }}
                fontSize={12}
              />
              <YAxis
                domain={[0, 1]}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                label={{ value: "Realized Frequency", angle: -90, position: "insideLeft" }}
                fontSize={12}
              />
              <Tooltip
                formatter={(v: any) => `${(Number(v) * 100).toFixed(1)}%`}
                labelFormatter={(v) => `Predicted: ${(Number(v) * 100).toFixed(0)}%`}
              />
              <Legend verticalAlign="top" height={legendHeight} />
              <ReferenceLine
                segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]}
                stroke="#9ca3af"
                strokeDasharray="5 5"
              />

              {view === "by-category" &&
                selectedCats.map((cat) => {
                  const entry = dash.domain_time_matrix[cat]?.[selectedHorizon];
                  if (!entry) return null;
                  return (
                    <Line
                      key={cat}
                      data={entry.cal_curve}
                      type="monotone"
                      dataKey="realized_frequency"
                      stroke={CAT_COLORS[cat] || "#666"}
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      name={`${cat} (BS=${entry.brier.toFixed(3)}, n=${entry.n})`}
                    />
                  );
                })}

              {view === "by-time" &&
                Object.entries(dash.time_horizon_calibration).map(([label, bins], i) => (
                  <Line
                    key={label}
                    data={bins}
                    type="monotone"
                    dataKey="realized_frequency"
                    stroke={["#ef4444", "#f59e0b", "#10b981", "#2563eb"][i] || "#666"}
                    strokeWidth={2}
                    dot={{ r: 4 }}
                    name={`${label} (BS=${bins[0]?.brier_score?.toFixed(4) ?? "?"})`}
                  />
                ))}

              {view === "by-liquidity" &&
                Object.entries(dash.liquidity_calibration).map(([bucket, bins]) => {
                  const colors: Record<string, string> = { low: "#ef4444", medium: "#f59e0b", high: "#10b981" };
                  return (
                    <Line
                      key={bucket}
                      data={bins}
                      type="monotone"
                      dataKey="realized_frequency"
                      stroke={colors[bucket] || "#666"}
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      name={`${bucket} volume (BS=${bins[0]?.brier_score?.toFixed(4) ?? "?"})`}
                    />
                  );
                })}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Summary stats for selected slice */}
      <div className="card">
        <div className="stats-grid">
          {view === "by-category" && selectedCats.map((cat) => {
            const entry = dash.domain_time_matrix[cat]?.[selectedHorizon];
            if (!entry) return null;
            return (
              <div key={cat} className="stat-card" style={{ borderTop: `3px solid ${CAT_COLORS[cat] || "#666"}` }}>
                <div className="stat-value">{entry.brier.toFixed(4)}</div>
                <div className="stat-label">{cat}</div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>
                  {entry.n.toLocaleString()} obs, {entry.n_markets} markets
                </div>
              </div>
            );
          })}
          {view === "by-time" && Object.entries(dash.time_horizon_calibration).map(([label, bins]) => {
            const b = bins[0];
            if (!b) return null;
            return (
              <div key={label} className="stat-card">
                <div className="stat-value">{b.brier_score?.toFixed(4) ?? "---"}</div>
                <div className="stat-label">{label}</div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>
                  {b.n_observations?.toLocaleString() ?? "?"} obs, {b.n_markets ?? "?"} markets
                </div>
              </div>
            );
          })}
          {view === "by-liquidity" && Object.entries(dash.liquidity_calibration).map(([bucket, bins]) => {
            const b = bins[0];
            if (!b) return null;
            return (
              <div key={bucket} className="stat-card">
                <div className="stat-value">{b.brier_score?.toFixed(4) ?? "---"}</div>
                <div className="stat-label">{bucket} volume</div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>
                  {b.n_observations?.toLocaleString() ?? "?"} obs, {b.n_markets ?? "?"} markets
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Interpretation */}
      <div className="card">
        <h3>How to Read This</h3>
        <p style={{ fontSize: "0.85rem", color: "var(--gray-700)", lineHeight: 1.8 }}>
          <strong>Perfect calibration</strong> follows the dashed diagonal. Points above the line = underconfident (happens more often than the price suggests). Points below = overconfident.
        </p>
      </div>
    </div>
  );
}
