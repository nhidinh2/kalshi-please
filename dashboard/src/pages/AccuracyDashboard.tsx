import { useDashboardData, useSummary } from "../hooks/useData";
import { catColor, TIME_HORIZONS, TIME_COLORS } from "../constants";
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

// Average that treats a genuine 0.0 as a value, not as absent. The old code used
// .filter(Boolean), which drops 0.0 — and Elections/Social sit near there.
function mean(vals: (number | null | undefined)[]): number | null {
  const nums = vals.filter((v): v is number => typeof v === "number");
  if (nums.length === 0) return null;
  return nums.reduce((s, v) => s + v, 0) / nums.length;
}

export function AccuracyDashboard() {
  const { data: summary, loading: ls } = useSummary();
  const { data: dash, loading: ld } = useDashboardData();

  if (ls || ld) return <div className="loading">Loading...</div>;
  if (!summary || !dash) return <div className="loading">No data available.</div>;

  const catStats = summary.category_stats;

  // Brier by category, one day before close. This is the real forecasting test:
  // the last-tick price flatters categories whose outcome becomes public before
  // the market closes (a called election trades at 0.99 for days). Categories
  // with fewer than 5 markets that far out are dropped as too thin to trust.
  const catBrier = Object.entries(catStats)
    .filter(([, s]) => s.brier_1d_before != null && s.n_markets_1d >= 5)
    .map(([cat, s]) => ({
      category: cat,
      brier: s.brier_1d_before as number,
      brierLast: s.brier_last_tick,
      n: s.n_markets_1d,
    }))
    .sort((a, b) => a.brier - b.brier);

  // Brier by time horizon
  const timeBrier = Object.entries(dash.time_horizon_calibration).map(([label, bins]) => ({
    horizon: label,
    brier: bins[0]?.brier_score ?? 0,
    n: bins[0]?.n_observations ?? 0,
  }));

  // Domain x time heatmap data
  const matrix = dash.domain_time_matrix;
  const heatmapRows = Object.entries(matrix)
    .filter(([, horizons]) => Object.keys(horizons).length > 0)
    .map(([cat, horizons]) => {
      const row: Record<string, string | number | null> = { category: cat };
      for (const h of TIME_HORIZONS) row[h] = horizons[h]?.brier ?? null;
      return row;
    })
    .sort((a, b) => {
      const aAvg = mean(TIME_HORIZONS.map((h) => a[h] as number | null)) ?? Infinity;
      const bAvg = mean(TIME_HORIZONS.map((h) => b[h] as number | null)) ?? Infinity;
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
          <div className="stat-value">{summary.overall_brier_1d_before ?? "—"}</div>
          <div className="stat-label">Brier, 1 Day Before Close</div>
        </div>
      </div>

      {/* Brier by category */}
      <div className="card">
        <h2>Forecast Accuracy by Category</h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
          Brier score one day before the market closes (lower = more accurate) —
          the price while the outcome is still genuinely uncertain. The faint bar
          is the last traded price, which for many markets is set after the result
          is already public and so overstates accuracy. Categories with fewer than
          5 markets one day out are omitted.
        </p>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={catBrier} layout="vertical" margin={{ left: 120, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis type="number" domain={[0, "auto"]} fontSize={12} />
              <YAxis type="category" dataKey="category" width={115} fontSize={11} />
              <Tooltip
                formatter={(v, name) => [Number(v).toFixed(4), String(name)]}
                labelFormatter={(l) => {
                  const item = catBrier.find((c) => c.category === l);
                  return `${l} (n=${item?.n ?? "?"})`;
                }}
              />
              <Bar dataKey="brierLast" radius={[0, 4, 4, 0]} name="Last tick" fillOpacity={0.25}>
                {catBrier.map((entry) => (
                  <Cell key={entry.category} fill={catColor(entry.category)} />
                ))}
              </Bar>
              <Bar dataKey="brier" radius={[0, 4, 4, 0]} name="1 day before">
                {catBrier.map((entry) => (
                  <Cell key={entry.category} fill={catColor(entry.category)} />
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
                    const val = row[h] as number | null;
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
