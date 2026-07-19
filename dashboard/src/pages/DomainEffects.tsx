import { useState } from "react";
import { useDashboardData } from "../hooks/useData";
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
  ScatterChart,
  Scatter,
  ZAxis,
  ErrorBar,
  Legend,
  ReferenceLine,
} from "recharts";

export function DomainEffects() {
  const { data: dash, loading } = useDashboardData();
  const [detailsOpen, setDetailsOpen] = useState(false);

  if (loading) return <div className="loading">Loading...</div>;
  if (!dash?.explanatory) return <div className="loading">No explanatory data available.</div>;

  const { correlations, category_profiles, category_correlations, narratives } = dash.explanatory;
  const reg = dash.regression;

  const profilesSorted = [...category_profiles]
    .filter((p) => p.n_markets >= 5)
    .sort((a, b) => b.brier_score - a.brier_score);

  const corrData = correlations
    .filter((c) => c.significant)
    .sort((a, b) => Math.abs(b.spearman_r) - Math.abs(a.spearman_r));

  const catCorrData = category_correlations
    .sort((a, b) => Math.abs(b.spearman_r) - Math.abs(a.spearman_r));

  const domainCoefs = reg?.domain_coefficients
    ?.filter((d) => d.coef_no_controls != null)
    .sort((a, b) => (b.coef_with_controls ?? 0) - (a.coef_with_controls ?? 0)) ?? [];

  // Bootstrap CI data
  const ciData = dash.recalibration?.confidence_intervals
    ? [...dash.recalibration.confidence_intervals]
        .sort((a, b) => b.effect - a.effect)
        .map((d) => ({
          ...d,
          errorRange: [d.effect - d.ci_lower, d.ci_upper - d.effect] as [number, number],
        }))
    : [];

  return (
    <div>
      {/* ── Headline: The Verdict ── */}
      {reg && (
        <div className="card" style={{
          borderLeft: `4px solid ${reg.r2_lift > 0.01 ? "#2563eb" : "#10b981"}`,
          background: reg.r2_lift > 0.01 ? "rgba(37, 99, 235, 0.04)" : "rgba(16, 185, 129, 0.04)",
        }}>
          <h2>Do Domain Effects Survive Controls?</h2>
          <p style={{ fontSize: "1rem", lineHeight: 1.7, marginBottom: "1rem" }}>
            {reg.verdict}
          </p>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-value">{(reg.r2_with_domain * 100).toFixed(1)}%</div>
              <div className="stat-label">R² with domain</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{(reg.r2_without_domain * 100).toFixed(1)}%</div>
              <div className="stat-label">R² without domain</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">+{(reg.r2_lift * 100).toFixed(1)}%</div>
              <div className="stat-label">R² lift from domain</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{reg.surviving_domains.length}/{domainCoefs.length}</div>
              <div className="stat-label">Domains survive controls</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{reg.n_sig_interactions}/{reg.n_interactions}</div>
              <div className="stat-label">Significant interactions</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Model Comparison Table ── */}
      {reg && (
        <div className="card">
          <h2>Model Comparison</h2>
          <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
            Five OLS models testing whether domain (category) predicts squared forecast error
            after controlling for volume, spread, duration, price range, and base rate imbalance.
            Reference category: {reg.reference_category}.
          </p>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th style={{ textAlign: "center" }}>R²</th>
                  <th style={{ textAlign: "center" }}>Adj R²</th>
                  <th style={{ textAlign: "center" }}>AIC</th>
                  <th style={{ textAlign: "center" }}>n</th>
                </tr>
              </thead>
              <tbody>
                {reg.model_comparison.map((m) => {
                  const isBest = m.model === "Domain x horizon + controls";
                  return (
                    <tr key={m.model} style={{ fontWeight: isBest ? 700 : 400 }}>
                      <td>{m.model}</td>
                      <td style={{ textAlign: "center" }}>{(m.r2 * 100).toFixed(2)}%</td>
                      <td style={{ textAlign: "center" }}>{(m.adj_r2 * 100).toFixed(2)}%</td>
                      <td style={{ textAlign: "center" }}>{m.aic.toFixed(0)}</td>
                      <td style={{ textAlign: "center" }}>{m.n.toLocaleString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Domain Coefficients: Before vs After Controls ── */}
      {domainCoefs.length > 0 && (
        <div className="card">
          <h2>Domain Effects: Before vs After Controls</h2>
          <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
            OLS coefficient for each category relative to {reg.reference_category}.
            Positive = worse calibration. Stars mark coefficients that remain significant (p&lt;0.05) after adding controls.
          </p>
          <div className="chart-container" style={{ height: Math.max(300, domainCoefs.length * 35) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={domainCoefs} layout="vertical" margin={{ left: 130, right: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" fontSize={12} />
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
                        <br />Before controls: {d.coef_no_controls?.toFixed(4)} (p={d.p_no_controls?.toFixed(4)})
                        <br />After controls: {d.coef_with_controls?.toFixed(4)} (p={d.p_with_controls?.toFixed(4)})
                        <br />{d.survives ? "Survives controls" : "Does not survive"}
                      </div>
                    );
                  }}
                />
                <Bar dataKey="coef_no_controls" name="Before controls" fill="#fca5a5" radius={[0, 4, 4, 0]} />
                <Bar dataKey="coef_with_controls" name="After controls" radius={[0, 4, 4, 0]}>
                  {domainCoefs.map((d) => (
                    <Cell
                      key={d.category}
                      fill={d.survives
                        ? (d.coef_with_controls > 0 ? "#ef4444" : "#10b981")
                        : "#d1d5db"
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p style={{ color: "var(--gray-500)", fontSize: "0.8rem", marginTop: "0.5rem" }}>
            Light red = before controls. Colored = after controls (red = worse, green = better, gray = not significant).
          </p>
        </div>
      )}

      {/* ── Bootstrap CIs ── */}
      {ciData.length > 0 && (
        <div className="card">
          <h2>Domain Effects with 95% Bootstrap CIs</h2>
          <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
            Point estimates and 95% confidence intervals for each category's effect
            relative to {dash.recalibration?.reference_category ?? "Politics"}. Filled bars are statistically significant (CI excludes 0).
          </p>
          <div className="chart-container" style={{ height: Math.max(300, ciData.length * 40) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ciData} layout="vertical" margin={{ left: 130, right: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" fontSize={12} />
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
                        <br />Effect: {d.effect.toFixed(4)}
                        <br />95% CI: [{d.ci_lower.toFixed(4)}, {d.ci_upper.toFixed(4)}]
                        <br />{d.significant ? "Significant" : "Not significant"}
                      </div>
                    );
                  }}
                />
                <Legend />
                <ReferenceLine x={0} stroke="#6b7280" strokeDasharray="3 3" />
                <Bar dataKey="effect" name="Domain effect" radius={[0, 4, 4, 0]}>
                  {ciData.map((d) => (
                    <Cell
                      key={d.category}
                      fill={d.significant
                        ? (d.effect > 0 ? "#ef4444" : "#10b981")
                        : "#d1d5db"
                      }
                      fillOpacity={d.significant ? 1 : 0.6}
                    />
                  ))}
                  <ErrorBar
                    dataKey="errorRange"
                    width={4}
                    strokeWidth={2}
                    stroke="#374151"
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p style={{ color: "var(--gray-500)", fontSize: "0.8rem", marginTop: "0.5rem" }}>
            Colored = significant (red = worse, green = better). Gray = not significant. Error bars show bootstrap 95% CI.
          </p>
        </div>
      )}

      {/* ── Accordion: Supporting Diagnostics ── */}
      <div className="card">
        <div
          onClick={() => setDetailsOpen(!detailsOpen)}
          style={{
            cursor: "pointer",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            userSelect: "none",
          }}
        >
          <h2 style={{ margin: 0 }}>Supporting Diagnostics</h2>
          <span style={{ fontSize: "1.2rem", color: "var(--gray-500)", transition: "transform 0.2s", transform: detailsOpen ? "rotate(180deg)" : "rotate(0)" }}>
            ▼
          </span>
        </div>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginTop: "0.5rem" }}>
          Control variable effects, category narratives, feature correlations, and profile scatter plots.
        </p>
      </div>

      {detailsOpen && (
        <>
          {/* ── Control Variables ── */}
          {reg?.control_coefficients && reg.control_coefficients.length > 0 && (
            <div className="card">
              <h2>Control Variable Effects</h2>
              <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
                Market microstructure variables included as controls. These capture the "how" — but domain
                effects persist even after accounting for them.
              </p>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Feature</th>
                      <th style={{ textAlign: "center" }}>Coefficient</th>
                      <th style={{ textAlign: "center" }}>p-value</th>
                      <th style={{ textAlign: "center" }}>Significant</th>
                      <th style={{ textAlign: "center" }}>Direction</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reg.control_coefficients.map((c) => (
                      <tr key={c.feature}>
                        <td style={{ fontWeight: 600 }}>{c.feature.replace(/_/g, " ").replace("cat ", "")}</td>
                        <td style={{ textAlign: "center", fontFamily: "monospace" }}>{c.coefficient.toFixed(6)}</td>
                        <td style={{ textAlign: "center" }}>{c.p_value.toFixed(4)}</td>
                        <td style={{ textAlign: "center" }}>{c.significant ? "Yes" : "No"}</td>
                        <td style={{ textAlign: "center", color: c.coefficient > 0 ? "#ef4444" : "#10b981" }}>
                          {c.coefficient > 0 ? "Worse" : "Better"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Narratives ── */}
          <div className="card">
            <h2>Category Narratives</h2>
            <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
              Auto-generated explanations based on each category's feature profile.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {profilesSorted.map((p) => {
                const n = narratives[p.category];
                if (!n) return null;
                const bgColor =
                  n.quality === "poorly calibrated"
                    ? "rgba(239, 68, 68, 0.08)"
                    : n.quality === "moderately calibrated"
                    ? "rgba(245, 158, 11, 0.08)"
                    : "rgba(16, 185, 129, 0.08)";
                const borderColor =
                  n.quality === "poorly calibrated"
                    ? "#ef4444"
                    : n.quality === "moderately calibrated"
                    ? "#f59e0b"
                    : "#10b981";
                return (
                  <div
                    key={p.category}
                    style={{
                      padding: "0.75rem 1rem",
                      background: bgColor,
                      borderLeft: `4px solid ${borderColor}`,
                      borderRadius: "0 6px 6px 0",
                      fontSize: "0.85rem",
                      lineHeight: 1.6,
                    }}
                  >
                    <span style={{ color: catColor(p.category), fontWeight: 700 }}>
                      {p.category}
                    </span>{" "}
                    {n.text.slice(n.text.indexOf("markets are") + 7)}
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── Feature Correlations ── */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="card">
              <h2 style={{ fontSize: "1rem" }}>Market-Level Correlations</h2>
              <p style={{ color: "var(--gray-500)", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
                Spearman r with Brier score. Significant only (p&lt;0.05).
              </p>
              <div className="chart-container" style={{ height: Math.max(200, corrData.length * 35) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={corrData} layout="vertical" margin={{ left: 120, right: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis type="number" domain={[-0.5, 0.5]} fontSize={11} />
                    <YAxis type="category" dataKey="label" width={115} fontSize={10} />
                    <Tooltip formatter={(v: any) => `r = ${Number(v).toFixed(4)}`} />
                    <Bar dataKey="spearman_r" name="Spearman r" radius={[0, 4, 4, 0]}>
                      {corrData.map((entry) => (
                        <Cell key={entry.feature} fill={entry.spearman_r > 0 ? "#ef4444" : "#10b981"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="card">
              <h2 style={{ fontSize: "1rem" }}>Category-Level Correlations</h2>
              <p style={{ color: "var(--gray-500)", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
                Spearman r of category medians with category Brier.
              </p>
              <div className="chart-container" style={{ height: Math.max(200, catCorrData.length * 35) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={catCorrData} layout="vertical" margin={{ left: 120, right: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis type="number" domain={[-1, 1]} fontSize={11} />
                    <YAxis type="category" dataKey="label" width={115} fontSize={10} />
                    <Tooltip formatter={(v: any) => `r = ${Number(v).toFixed(3)}`} />
                    <Bar dataKey="spearman_r" name="Spearman r" radius={[0, 4, 4, 0]}>
                      {catCorrData.map((entry) => (
                        <Cell
                          key={entry.feature}
                          fill={entry.significant ? (entry.spearman_r > 0 ? "#ef4444" : "#10b981") : "#d1d5db"}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* ── Category Profiles Scatter ── */}
          <div className="card">
            <h2>Category Feature Profiles</h2>
            <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
              Each dot is a category. Size = number of markets.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              {([
                ["avg_spread", "Bid-Ask Spread"],
                ["late_price_move", "Late Price Move"],
                ["n_price_observations", "# Price Updates"],
                ["total_volume", "Total Volume"],
              ] as [string, string][]).map(([key, label]) => (
                <div key={key} className="chart-container" style={{ height: 250 }}>
                  <h4 style={{ fontSize: "0.85rem", marginBottom: "0.25rem" }}>{label} vs Brier</h4>
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 5, right: 20, bottom: 20, left: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="x" type="number" fontSize={10} name={label}
                        label={{ value: label, position: "bottom", offset: 5, fontSize: 10 }} />
                      <YAxis dataKey="y" type="number" fontSize={10} name="Brier"
                        label={{ value: "Brier", angle: -90, position: "insideLeft", fontSize: 10 }} />
                      <ZAxis dataKey="z" range={[40, 400]} />
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
                              <br />{label}: {d.x?.toFixed(4) ?? "N/A"}
                              <br />Brier: {d.y?.toFixed(4)}
                              <br />Markets: {d.z}
                            </div>
                          );
                        }}
                      />
                      <Scatter
                        data={profilesSorted
                          .filter((p) => p[key as keyof typeof p] != null)
                          .map((p) => ({
                            x: p[key as keyof typeof p] as number,
                            y: p.brier_score,
                            z: p.n_markets,
                            category: p.category,
                          }))}
                      >
                        {profilesSorted
                          .filter((p) => p[key as keyof typeof p] != null)
                          .map((p) => (
                            <Cell key={p.category} fill={catColor(p.category)} />
                          ))}
                      </Scatter>
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
