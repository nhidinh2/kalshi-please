import { useState, useMemo } from "react";
import { useDashboardData, useMarketFeatures } from "../hooks/useData";
import type { MarketFeature } from "../types";
import { catColor } from "../constants";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
  ReferenceLine,
  LineChart,
  Line,
} from "recharts";

type SortKey = keyof MarketFeature;

export function PracticalUse() {
  const { data: dash, loading: ld } = useDashboardData();
  const { data: markets, loading: lm } = useMarketFeatures();
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("total_volume");
  const [sortDesc, setSortDesc] = useState(true);
  const [selectedMarket, setSelectedMarket] = useState<MarketFeature | null>(null);

  const categories = useMemo(
    () => ["all", ...new Set(markets.map((m) => m.category).filter(Boolean))].sort(),
    [markets]
  );

  const filtered = useMemo(() => {
    return markets
      .filter((m) => {
        if (categoryFilter !== "all" && m.category !== categoryFilter) return false;
        if (search) {
          const s = search.toLowerCase();
          return (
            m.market_ticker.toLowerCase().includes(s) ||
            (m.event_title || "").toLowerCase().includes(s) ||
            (m.yes_sub_title || "").toLowerCase().includes(s)
          );
        }
        return true;
      })
      .sort((a, b) => {
        const va = a[sortKey];
        const vb = b[sortKey];
        const dir = sortDesc ? -1 : 1;
        // Nulls always sort last, regardless of direction.
        const aNull = va === null || va === undefined;
        const bNull = vb === null || vb === undefined;
        if (aNull && bNull) return 0;
        if (aNull) return 1;
        if (bNull) return -1;
        if (typeof va === "string" && typeof vb === "string") {
          return dir * va.localeCompare(vb);
        }
        return dir * (Number(va) - Number(vb));
      });
  }, [markets, search, categoryFilter, sortKey, sortDesc]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDesc(!sortDesc);
    else { setSortKey(key); setSortDesc(true); }
  };

  if (ld || lm) return <div className="loading">Loading...</div>;

  const recal = dash?.recalibration;

  const improvementsSorted = recal
    ? [...recal.category_improvements].sort((a, b) => b.improvement_pct - a.improvement_pct)
    : [];

  return (
    <div>
      {/* ── Recalibration Summary ── */}
      {recal && (
        <div className="card" style={{
          borderLeft: "4px solid #8b5cf6",
          background: "rgba(139, 92, 246, 0.04)",
        }}>
          <h2>Out-of-Sample Recalibration ({recal.n_folds}-Fold CV)</h2>
          <p style={{ fontSize: "0.9rem", lineHeight: 1.7, marginBottom: "1rem", color: "var(--gray-700)" }}>
            A domain-aware recalibration layer adjusts raw market prices using Platt scaling
            per (category, horizon) group. Averaged over {recal.n_seeds} cross-validation
            splits, the overall improvement is{" "}
            <strong>{recal.improvement_mean_pct >= 0 ? "+" : ""}{recal.improvement_mean_pct.toFixed(1)}%
            ± {recal.improvement_se_pct.toFixed(1)}% (SE)</strong> —{" "}
            {recal.improvement_reliable
              ? "a reliable effect."
              : "indistinguishable from zero. The layer does not improve calibration overall; " +
                "the single-split figure below is mostly split noise. It helps where miscalibration " +
                "is large (below) and hurts small or already-good categories."}
          </p>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-value">{recal.raw_brier.toFixed(4)}</div>
              <div className="stat-label">Raw Brier</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{recal.recalibrated_brier.toFixed(4)}</div>
              <div className="stat-label">Recalibrated Brier (1 split)</div>
            </div>
            <div className="stat-card">
              <div
                className="stat-value"
                style={{ color: recal.improvement_reliable && recal.improvement_mean_pct > 0 ? "#10b981" : "#6b7280" }}
              >
                {recal.improvement_mean_pct >= 0 ? "+" : ""}{recal.improvement_mean_pct.toFixed(1)}%
              </div>
              <div className="stat-label">Mean improvement ({recal.n_seeds} splits)</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ fontSize: "1.1rem" }}>
                [{recal.improvement_range_pct[0].toFixed(1)}%, {recal.improvement_range_pct[1].toFixed(1)}%]
              </div>
              <div className="stat-label">Range across splits</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{recal.n_markets.toLocaleString()}</div>
              <div className="stat-label">Markets</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Per-Category Improvement ── */}
      {improvementsSorted.length > 0 && (
        <div className="card">
          <h2>Per-Category Brier Improvement</h2>
          <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
            Percentage improvement in Brier score from recalibration, by category.
            Green = improvement, red = degradation.
          </p>
          <div className="chart-container" style={{ height: Math.max(300, improvementsSorted.length * 35) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={improvementsSorted} layout="vertical" margin={{ left: 130, right: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" fontSize={12} tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="category" width={125} fontSize={10} />
                <Tooltip
                  content={({ payload }) => {
                    if (!payload?.[0]) return null;
                    const d = payload[0].payload;
                    return (
                      <div style={{
                        background: "white", border: "1px solid #e5e7eb",
                        padding: "0.5rem", borderRadius: 4, fontSize: "0.8rem",
                      }}>
                        <strong style={{ color: catColor(d.category) }}>{d.category}</strong>
                        <br />Raw Brier: {d.raw_brier.toFixed(4)}
                        <br />Recalibrated: {d.recalibrated_brier.toFixed(4)}
                        <br />Improvement: {d.improvement_pct > 0 ? "+" : ""}{d.improvement_pct.toFixed(1)}%
                        <br />Test samples: {d.n_test.toLocaleString()}
                      </div>
                    );
                  }}
                />
                <ReferenceLine x={0} stroke="#6b7280" strokeDasharray="3 3" />
                <Bar dataKey="improvement_pct" name="Improvement %" radius={[0, 4, 4, 0]}>
                  {improvementsSorted.map((d) => (
                    <Cell
                      key={d.category}
                      fill={d.improvement_pct >= 0 ? "#10b981" : "#ef4444"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── Market Explorer ── */}
      {selectedMarket && (
        <MarketDetail market={selectedMarket} onClose={() => setSelectedMarket(null)} />
      )}

      <div className="card">
        <h2>Market Explorer</h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
          Click a market to see its price path, volume, and final outcome.
        </p>
        <div className="filters">
          <input
            type="text"
            placeholder="Search markets..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ minWidth: 200 }}
          />
          <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
            {categories.map((c) => (
              <option key={c} value={c}>{c === "all" ? "All categories" : c}</option>
            ))}
          </select>
          <span style={{ color: "var(--gray-500)", fontSize: "0.85rem" }}>
            {filtered.length} markets
          </span>
        </div>
      </div>

      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th onClick={() => handleSort("yes_sub_title")}>Market</th>
                <th onClick={() => handleSort("category")}>Category</th>
                <th onClick={() => handleSort("result")}>Result</th>
                <th onClick={() => handleSort("last_price")}>Final Price</th>
                <th onClick={() => handleSort("total_volume")}>Volume</th>
                <th onClick={() => handleSort("duration_hours")}>Duration</th>
                <th onClick={() => handleSort("brier_score")}>Brier</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 100).map((m) => (
                <tr
                  key={m.market_ticker}
                  style={{ cursor: "pointer" }}
                  onClick={() => setSelectedMarket(m)}
                >
                  <td title={m.market_ticker}>
                    {(m.yes_sub_title || m.event_title || m.market_ticker).slice(0, 50)}
                  </td>
                  <td>
                    <span style={{
                      color: catColor(m.category),
                      fontWeight: 600,
                      fontSize: "0.8rem",
                    }}>
                      {m.category}
                    </span>
                  </td>
                  <td><span className={`badge badge-${m.result}`}>{m.result}</span></td>
                  <td>{m.last_price != null ? `${(m.last_price * 100).toFixed(0)}%` : "---"}</td>
                  <td>{m.total_volume != null ? Math.round(m.total_volume).toLocaleString() : "---"}</td>
                  <td>{m.duration_hours != null ? `${Math.round(m.duration_hours / 24)}d` : "---"}</td>
                  <td>{m.brier_score != null ? m.brier_score.toFixed(4) : "---"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length > 100 && (
            <p style={{ textAlign: "center", padding: "0.5rem", color: "var(--gray-500)", fontSize: "0.85rem" }}>
              Showing 100 of {filtered.length}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function MarketDetail({ market, onClose }: { market: MarketFeature; onClose: () => void }) {
  const pricePoints = useMemo(() => {
    const points: { label: string; price: number; daysOut: number }[] = [];
    if (market.price_7d_before != null)
      points.push({ label: "7d before", price: market.price_7d_before * 100, daysOut: 7 });
    if (market.price_3d_before != null)
      points.push({ label: "3d before", price: market.price_3d_before * 100, daysOut: 3 });
    if (market.price_1d_before != null)
      points.push({ label: "1d before", price: market.price_1d_before * 100, daysOut: 1 });
    if (market.last_price != null)
      points.push({ label: "Final", price: market.last_price * 100, daysOut: 0 });
    return points;
  }, [market]);

  const outcome = market.result_binary * 100;

  return (
    <div className="card" style={{ borderColor: catColor(market.category), borderWidth: 2 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
        <div>
          <h2 style={{ fontSize: "1.1rem" }}>
            {market.yes_sub_title || market.event_title || market.market_ticker}
          </h2>
          <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginTop: "0.25rem" }}>
            {market.market_ticker} |{" "}
            <span style={{ color: catColor(market.category), fontWeight: 600 }}>{market.category}</span> |{" "}
            Resolved <span className={`badge badge-${market.result}`}>{market.result.toUpperCase()}</span>
          </p>
        </div>
        <button onClick={onClose} style={{ cursor: "pointer", border: "none", background: "none", fontSize: "1.5rem", color: "#999" }}>
          &times;
        </button>
      </div>

      <div className="stats-grid" style={{ marginTop: "1rem" }}>
        <div className="stat-card">
          <div className="stat-value">{market.last_price != null ? `${(market.last_price * 100).toFixed(1)}%` : "---"}</div>
          <div className="stat-label">Final Price</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{market.total_volume != null ? Math.round(market.total_volume).toLocaleString() : "---"}</div>
          <div className="stat-label">Total Volume</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{market.duration_hours != null ? `${Math.round(market.duration_hours / 24)}d` : "---"}</div>
          <div className="stat-label">Duration</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{market.brier_score != null ? market.brier_score.toFixed(4) : "---"}</div>
          <div className="stat-label">Brier Score</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{market.avg_spread != null ? `${(market.avg_spread * 100).toFixed(1)}%` : "---"}</div>
          <div className="stat-label">Avg Spread</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{market.n_price_observations ?? "---"}</div>
          <div className="stat-label">Observations</div>
        </div>
      </div>

      {pricePoints.length > 1 && (
        <div style={{ height: 280, marginTop: "1rem" }}>
          <h3>Price Path to Resolution</h3>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={pricePoints} margin={{ top: 10, right: 30, bottom: 10, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="label" fontSize={12} />
              <YAxis domain={[0, 100]} fontSize={12} tickFormatter={(v) => `${v}%`} />
              <Tooltip formatter={(v: any) => `${Number(v).toFixed(1)}%`} />
              <ReferenceLine y={outcome} stroke={market.result === "yes" ? "#10b981" : "#ef4444"}
                strokeDasharray="5 5" label={`Outcome: ${market.result.toUpperCase()}`} />
              <Line type="monotone" dataKey="price" stroke={catColor(market.category)}
                strokeWidth={3} dot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
