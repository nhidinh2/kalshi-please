import { useDashboardData, useSummary } from "../hooks/useData";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
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
const TIME_COLORS = ["#ef4444", "#f59e0b", "#10b981", "#2563eb"];

export function AccuracyDashboard() {
  const { data: summary, loading: ls } = useSummary();
  const { data: dash, loading: ld } = useDashboardData();

  if (ls || ld) return <div className="loading">Loading...</div>;
  if (!summary || !dash) return <div className="loading">No data available.</div>;

  const catStats = summary.category_stats;

  // Brier by category bar chart data
  const catBrier = Object.entries(catStats)
    .map(([cat, stats]) => ({ category: cat, brier: stats.brier, n: stats.n_markets }))
    .sort((a, b) => a.brier - b.brier);

  // Brier by time horizon
  const timeBrier = Object.entries(dash.time_horizon_calibration)
    .map(([label, bins]) => ({
      horizon: label,
      brier: bins[0]?.brier_score ?? 0,
      n: bins[0]?.n_observations ?? 0,
    }));

  // Domain x time heatmap data
  const matrix = dash.domain_time_matrix;
  const heatmapRows = Object.entries(matrix)
    .filter(([_, horizons]) => Object.keys(horizons).length > 0)
    .map(([cat, horizons]) => {
      const row: any = { category: cat };
      for (const h of TIME_HORIZONS) {
        row[h] = horizons[h]?.brier ?? null;
      }
      return row;
    })
    .sort((a, b) => {
      const aAvg = TIME_HORIZONS.map((h) => a[h]).filter(Boolean).reduce((s: number, v: number) => s + v, 0) / Math.max(TIME_HORIZONS.map((h) => a[h]).filter(Boolean).length, 1);
      const bAvg = TIME_HORIZONS.map((h) => b[h]).filter(Boolean).reduce((s: number, v: number) => s + v, 0) / Math.max(TIME_HORIZONS.map((h) => b[h]).filter(Boolean).length, 1);
      return aAvg - bAvg;
    });

  return (
    <div>
      {/* Key metrics */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{summary.total_markets.toLocaleString()}</div>
          <div className="stat-label">Resolved Markets</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{summary.n_categories}</div>
          <div className="stat-label">Categories</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{summary.total_observations.toLocaleString()}</div>
          <div className="stat-label">Price Observations</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{summary.overall_brier_score}</div>
          <div className="stat-label">Overall Brier Score</div>
        </div>
      </div>

      {/* Brier by category */}
      <div className="card">
        <h2>Forecast Accuracy by Category</h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
          Brier score (lower = more accurate). Not all categories are equal.
        </p>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={catBrier} layout="vertical" margin={{ left: 120, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis type="number" domain={[0, "auto"]} fontSize={12} />
              <YAxis type="category" dataKey="category" width={115} fontSize={11} />
              <Tooltip
                formatter={(v: any) => Number(v).toFixed(4)}
                labelFormatter={(l) => {
                  const item = catBrier.find((c) => c.category === l);
                  return `${l} (n=${item?.n ?? "?"})`;
                }}
              />
              <Bar dataKey="brier" radius={[0, 4, 4, 0]} name="Brier Score">
                {catBrier.map((entry) => (
                  <Cell
                    key={entry.category}
                    fill={CAT_COLORS[entry.category] || "#6b7280"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Brier by time horizon */}
      <div className="card">
        <h2>Forecast Accuracy by Time to Resolution</h2>
        <div className="chart-container" style={{ height: 300 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={timeBrier} margin={{ left: 20, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="horizon" fontSize={11} />
              <YAxis fontSize={12} />
              <Tooltip formatter={(v: any) => Number(v).toFixed(4)} />
              <Bar dataKey="brier" radius={[4, 4, 0, 0]} name="Brier Score">
                {timeBrier.map((_, i) => (
                  <Cell key={i} fill={TIME_COLORS[i]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Domain x Time heatmap (as table) */}
      <div className="card">
        <h2>Category x Time Horizon (Brier Score)</h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
          Is a 70-cent contract in politics at 7 days equivalent to one in weather?
          Green = accurate, red = poor.
        </p>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Category</th>
                {TIME_HORIZONS.map((h) => (
                  <th key={h} style={{ textAlign: "center" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {heatmapRows.map((row) => (
                <tr key={row.category}>
                  <td style={{ fontWeight: 600 }}>{row.category}</td>
                  {TIME_HORIZONS.map((h) => {
                    const val = row[h];
                    if (val === null) return <td key={h} style={{ textAlign: "center", color: "#ccc" }}>---</td>;
                    // Color: green (0) to red (0.3)
                    const ratio = Math.min(val / 0.3, 1);
                    const r = Math.round(ratio * 220 + 30);
                    const g = Math.round((1 - ratio) * 180 + 40);
                    const bg = `rgba(${r}, ${g}, 50, 0.2)`;
                    return (
                      <td key={h} style={{ textAlign: "center", background: bg, fontWeight: 500 }}>
                        {val.toFixed(3)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
