import { useDashboardData, useSummary } from "../hooks/useData";

const TRUST_TABLE = [
  { domain: "Politics", brier: "0.056", trust: "High", color: "#10b981", notes: "Tight spreads, high volume, long duration" },
  { domain: "Entertainment", brier: "0.050", trust: "High (near resolution)", color: "#10b981", notes: "Improves from 0.190 to 0.050 over market life" },
  { domain: "Economics", brier: "0.068", trust: "Moderate", color: "#f59e0b", notes: "Reasonable microstructure" },
  { domain: "Crypto", brier: "0.085", trust: "Moderate (addressable)", color: "#f59e0b", notes: "After controls, coefficient flips negative — raw gap is microstructure" },
  { domain: "Sports", brier: "0.127", trust: "Low", color: "#ef4444", notes: "Noisy despite 4.6× more volume than Politics" },
  { domain: "Companies", brier: "0.168", trust: "Low", color: "#ef4444", notes: "Associated with wide spreads, late surprise moves" },
  { domain: "Mentions", brier: "0.244", trust: "Unreliable", color: "#991b1b", notes: "Few observations, wide spreads" },
  { domain: "Financials", brier: "0.245", trust: "Unreliable", color: "#991b1b", notes: "Worst at every horizon" },
];

const S: Record<string, React.CSSProperties> = {
  section: { marginBottom: "2.5rem" },
  h2: { fontSize: "1.25rem", fontWeight: 700, marginBottom: "1rem", paddingBottom: "0.5rem", borderBottom: "2px solid #e5e7eb" },
  h3: { fontSize: "1.05rem", fontWeight: 600, marginBottom: "0.75rem", color: "#374151" },
  p: { fontSize: "0.92rem", lineHeight: 1.75, color: "#374151", marginBottom: "0.75rem" },
  li: { fontSize: "0.92rem", lineHeight: 1.75, color: "#374151", marginBottom: "0.5rem" },
  metric: { fontWeight: 700, color: "#2563eb" },
  muted: { fontSize: "0.85rem", color: "#6b7280", fontStyle: "italic" as const },
  callout: {
    padding: "1rem 1.25rem",
    background: "rgba(37, 99, 235, 0.04)",
    borderLeft: "4px solid #2563eb",
    borderRadius: "0 6px 6px 0",
    marginBottom: "1rem",
  },
  calloutWarn: {
    padding: "1rem 1.25rem",
    background: "rgba(245, 158, 11, 0.04)",
    borderLeft: "4px solid #f59e0b",
    borderRadius: "0 6px 6px 0",
    marginBottom: "1rem",
  },
};

export function Report() {
  const { data: summary, loading: ls } = useSummary();
  const { data: dash, loading: ld } = useDashboardData();

  if (ls || ld) return <div className="loading">Loading...</div>;
  if (!summary || !dash) return <div className="loading">No data available.</div>;

  const reg = dash.regression;
  const recal = dash.recalibration;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      {/* ── Title ── */}
      <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 700, marginBottom: "0.5rem" }}>
          Kalshi Prediction Market Calibration
        </h1>
        <p style={{ ...S.muted, fontSize: "0.95rem" }}>
          A study of {summary.total_markets.toLocaleString()} resolved markets across{" "}
          {summary.n_categories} categories with {summary.total_observations.toLocaleString()} price observations
        </p>
      </div>

      {/* ── Research Question ── */}
      <div style={S.section}>
        <div style={S.callout}>
          <p style={{ ...S.p, marginBottom: 0, fontWeight: 500 }}>
            <strong>Research question:</strong> A 70-cent contract on Kalshi implies a 70% probability.
            But does that hold equally for politics at 30 days out versus crypto at 7 days out?
            And if not — what drives the difference, and can we correct it?
          </p>
        </div>
      </div>

      {/* ── 1. Main Finding ── */}
      <div style={S.section}>
        <h2 style={S.h2}>1. A 70% price does not mean the same thing everywhere</h2>
        <p style={S.p}>
          Calibration varies by <span style={S.metric}>4×</span> across categories.
          Politics resolves with a Brier score of <span style={S.metric}>0.056</span> while
          Financials sits at <span style={S.metric}>0.245</span>. A single global calibration
          threshold is misleading.
        </p>

        <div className="table-container" style={{ marginTop: "1rem" }}>
          <table>
            <thead>
              <tr>
                <th>Domain</th>
                <th style={{ textAlign: "center" }}>Brier</th>
                <th style={{ textAlign: "center" }}>Trust Level</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {TRUST_TABLE.map((row) => (
                <tr key={row.domain}>
                  <td style={{ fontWeight: 600 }}>{row.domain}</td>
                  <td style={{ textAlign: "center", fontFamily: "monospace" }}>{row.brier}</td>
                  <td style={{ textAlign: "center" }}>
                    <span style={{
                      color: row.color,
                      fontWeight: 600,
                      fontSize: "0.8rem",
                    }}>
                      {row.trust}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.82rem", color: "#6b7280" }}>{row.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p style={{ ...S.p, marginTop: "1rem" }}>
          Categories also differ in <em>how they respond to time</em>. Entertainment improves
          dramatically near resolution (0.190 → 0.050), while Crypto gets <em>worse</em> (0.135 → 0.302) —
          the opposite of most categories.
        </p>
      </div>

      {/* ── 2. What drives it ── */}
      <div style={S.section}>
        <h2 style={S.h2}>2. What is associated with poor calibration</h2>
        <p style={S.p}>
          At the category level (Spearman rank correlations with Brier score):
        </p>
        <ul style={{ paddingLeft: "1.5rem", marginBottom: "1rem" }}>
          <li style={S.li}>
            <strong>Late price moves</strong> (r=+0.72, p=0.005) — the strongest correlate.
            Categories with large last-minute price shifts tend to calibrate worse.
          </li>
          <li style={S.li}>
            <strong>Late volume concentration</strong> (r=+0.54, p=0.047) — back-loaded trading
            is associated with poorer price discovery.
          </li>
          <li style={S.li}>
            <strong>Short duration</strong> (r=−0.66) and <strong>few price updates</strong> (r=−0.61) —
            consistent with information aggregation requiring time.
          </li>
          <li style={S.li}>
            <strong>Wide bid-ask spreads</strong> (r=+0.27, p&lt;0.001 at market level) — suggesting
            less competition and noisier signals.
          </li>
        </ul>
        <p style={S.muted}>
          Note: These are associations, not causal claims. Correlations are computed using Spearman rank
          correlation between category-median feature values and category Brier scores.
        </p>
      </div>

      {/* ── 3. Controls ── */}
      <div style={S.section}>
        <h2 style={S.h2}>3. Domain effects survive microstructure controls</h2>
        <p style={S.p}>
          Five OLS models progressively add controls (volume, spread, duration, price range, base rate
          imbalance) to test whether domain effects are just proxies for microstructure:
        </p>

        {reg && (
          <>
            <div className="table-container" style={{ marginBottom: "1rem" }}>
              <table>
                <thead>
                  <tr>
                    <th>Model</th>
                    <th style={{ textAlign: "center" }}>R²</th>
                    <th style={{ textAlign: "center" }}>Adj R²</th>
                  </tr>
                </thead>
                <tbody>
                  {reg.model_comparison.map((m) => {
                    const isBest = m.model === "Domain x horizon + controls";
                    return (
                      <tr key={m.model} style={{ fontWeight: isBest ? 700 : 400 }}>
                        <td>{m.model}</td>
                        <td style={{ textAlign: "center" }}>{(m.r2 * 100).toFixed(1)}%</td>
                        <td style={{ textAlign: "center" }}>{(m.adj_r2 * 100).toFixed(1)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div style={S.callout}>
              <p style={{ ...S.p, marginBottom: 0 }}>
                <strong>R² lift from domain: +{(reg.r2_lift * 100).toFixed(1)}%.</strong> Controls
                account for roughly half the gap, but{" "}
                <span style={S.metric}>{reg.surviving_domains.length} of {reg.domain_coefficients.length}</span>{" "}
                categories remain significant (p&lt;0.05) after controls. Domain itself retains
                independent predictive power.{" "}
                {reg.n_sig_interactions} of {reg.n_interactions} domain × horizon interactions are
                significant — categories differ not just in level but in how they respond to time.
              </p>
            </div>
          </>
        )}

        <p style={S.p}>
          Domain effects are robust across five alternative control specifications
          (minimal, microstructure-only, full, no-spread, no-volume).
        </p>
      </div>

      {/* ── 4. Surprising cases ── */}
      <div style={S.section}>
        <h2 style={S.h2}>4. Surprising cases</h2>

        <h3 style={S.h3}>Crypto: the sign-flip</h3>
        <p style={S.p}>
          Raw coefficient: +0.11 (worse than Politics). After controls: −0.08 (better).
          The reversal is consistent with Crypto's short duration (median ~25 hrs vs ~1,975 for Politics).
          The duration coefficient alone (−0.000015/hr × ~1,950 hrs) accounts for a large share of the shift.
          The raw underperformance appears fully attributable to microstructure — longer-duration
          Crypto markets would likely calibrate as well as or better than Politics.
        </p>

        <h3 style={S.h3}>Science & Technology: the reverse flip</h3>
        <p style={S.p}>
          Raw: −0.07 (looks better than Politics). After controls: +0.04 (worse).
          Sci/Tech has a narrow price range (median 0.06 vs 0.25). The price range coefficient (+0.245/unit)
          provides a mechanical advantage that compresses squared errors regardless of forecast quality.
          The raw excellence appears partly an artifact of constrained outcome space.
        </p>

        <h3 style={S.h3}>Financials: half survives</h3>
        <p style={S.p}>
          Coefficient drops 47% from +0.38 to +0.20. Widest spreads (0.124), shortest duration (71 hrs),
          lowest volume (7.4K). Microstructure accounts for roughly half the gap, but the residual remains
          highly significant — consistent with financial outcomes being intrinsically harder to forecast.
        </p>

        <h3 style={S.h3}>Sports: volume ≠ accuracy</h3>
        <p style={S.p}>
          4.6× Politics' volume yet worse calibration. The volume coefficient is <em>positive</em> (+0.010),
          suggesting high volume here reflects uncertainty-driven trading rather than informative price discovery.
        </p>
      </div>

      {/* ── 5. Recalibration ── */}
      <div style={S.section}>
        <h2 style={S.h2}>5. Out-of-sample recalibration</h2>
        <p style={S.p}>
          5-fold cross-validation (split by market, no data leakage) with Platt scaling
          per (category, horizon) group:
        </p>

        {recal && (
          <>
            <ul style={{ paddingLeft: "1.5rem", marginBottom: "1rem" }}>
              <li style={S.li}>
                <strong>Overall: <span style={S.metric}>+{recal.improvement_pct.toFixed(1)}%</span> Brier
                improvement</strong> — modest but confirms the signal is real
              </li>
              <li style={S.li}>
                Financials: +86.4% — the worst-calibrated category benefits most
              </li>
              <li style={S.li}>
                Crypto: +27.3%, Social: +22.7%
              </li>
              <li style={S.li}>
                Small categories degrade (World −98.5%, Climate −47.1%) — insufficient data for stable fits
              </li>
              <li style={S.li}>
                <strong>Bootstrap CIs:</strong> 7 of 12 domain effects have 95% confidence intervals excluding zero
              </li>
            </ul>

            <div style={S.calloutWarn}>
              <p style={{ ...S.p, marginBottom: 0 }}>
                The recalibration layer helps most where it's needed most and fails where sample sizes
                are too small — the pattern expected from a real signal rather than overfitting.
                A domain-adjusted probability model (logistic regression with raw price + domain + horizon)
                achieves +8.4% Brier improvement out-of-sample over raw Platt scaling.
              </p>
            </div>
          </>
        )}
      </div>

      {/* ── 6. Bottom line ── */}
      <div style={S.section}>
        <h2 style={S.h2}>6. The bottom line</h2>
        <p style={S.p}>
          Market microstructure (spread, volume, duration) accounts for roughly half of the calibration
          differences across categories. But domain itself retains independent predictive power —
          11 of 12 categories remain statistically significant after controls, and the effect is
          robust across alternative control specifications.
        </p>
        <p style={S.p}>
          A platform-wide recalibration layer that adjusts raw prices by category and time horizon
          would produce more accurate probability signals. The out-of-sample test confirms this is
          exploitable, not just descriptive. For Crypto specifically, the calibration gap appears
          addressable through market design — longer duration and more frequent price updates
          would bring its microstructure profile closer to better-calibrated categories.
        </p>
      </div>

      {/* ── Limitations ── */}
      <div style={S.section}>
        <h2 style={S.h2}>Limitations</h2>
        <ul style={{ paddingLeft: "1.5rem" }}>
          <li style={S.li}>Sample skews toward recently settled markets; some categories have few markets</li>
          <li style={S.li}>Observation-level R² is 23% — substantial for cross-sectional data, but individual outcomes remain noisy</li>
          <li style={S.li}>Standard errors assume independence across observations within the same market; clustered SEs would strengthen inference</li>
          <li style={S.li}>Sample-size diagnostics show instability for some category effects at &lt;50% of data</li>
          <li style={S.li}>All correlations are associative, not causal</li>
        </ul>
      </div>

      {/* ── Methodology ── */}
      <div style={S.section}>
        <h2 style={S.h2}>Methodology</h2>
        <p style={S.p}>
          <strong>Data:</strong> {summary.total_markets} resolved binary markets from the Kalshi public API
          across {summary.n_categories} categories, with {summary.total_observations.toLocaleString()} price
          observations (daily candlesticks with hourly backfill for short-lived markets).
        </p>
        <p style={S.p}>
          <strong>Features:</strong> Per-market: duration, volume, bid-ask spread, prices at 1/3/7 days
          before resolution, late-stage volatility, late price move magnitude, price range, late volume share.
          Calibration dataset: each row is one (market, timestamp) observation.
        </p>
        <p style={S.p}>
          <strong>Analyses:</strong> (A) Accuracy over time at 4 horizons, (B) Domain × time interaction matrix,
          (C) Liquidity effect, (D) Explanatory correlations + category narratives,
          (E) Five OLS models with progressive controls + robustness across alternative control sets,
          (F) Out-of-sample recalibration with 5-fold CV and bootstrap CIs,
          (G) Domain-adjusted probability model + sample-size diagnostics.
        </p>
        <p style={S.p}>
          <strong>Tools:</strong> Python, pandas, statsmodels, scikit-learn, SQLite.
          Dashboard: React, TypeScript, Recharts.
        </p>
      </div>

      <div style={{ textAlign: "center", padding: "2rem 0", color: "#9ca3af", fontSize: "0.8rem" }}>
        Use the tabs above to explore the interactive charts and data.
      </div>
    </div>
  );
}
